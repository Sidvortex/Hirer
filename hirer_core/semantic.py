"""
Meaning-based matching with local models (sentence-transformers).

Settings, all optional environment variables:
  HIRER_EMBED_MODEL         embedding model name or local folder   (BAAI/bge-small-en-v1.5)
  HIRER_EMBED_QUERY_PREFIX  text put before the job description    (set automatically for bge / e5)
  HIRER_EMBED_DOC_PREFIX    text put before candidate text         (set automatically for e5)
  HIRER_EMBED_CHUNKS        pieces per candidate: profile + recent roles   (3)
  HIRER_RERANK_MODEL        cross-encoder for the second pass      (cross-encoder/ms-marco-MiniLM-L-6-v2)
  HIRER_CACHE_DIR           where candidate embeddings are kept    (~/.cache/hirer)
  HIRER_DISABLE_SEMANTIC    1 = switch all of this off, for servers with little memory
"""

import hashlib
import os
from pathlib import Path

import numpy as np

EMBED_MODEL = os.environ.get('HIRER_EMBED_MODEL', 'BAAI/bge-small-en-v1.5')
RERANK_MODEL = os.environ.get('HIRER_RERANK_MODEL', 'cross-encoder/ms-marco-MiniLM-L-6-v2')
CHUNKS = max(1, int(os.environ.get('HIRER_EMBED_CHUNKS', '3')))
CACHE_DIR = Path(os.environ.get('HIRER_CACHE_DIR', Path.home() / '.cache' / 'hirer'))
CACHE_KEEP = 5      # embedding files kept; the oldest are deleted


def _prefixes(model_name):
    name = model_name.lower()
    query = doc = ''
    if 'bge' in name and 'm3' not in name:
        query = 'Represent this sentence for searching relevant passages: '
    elif 'e5' in name:
        query, doc = 'query: ', 'passage: '
    return (os.environ.get('HIRER_EMBED_QUERY_PREFIX', query),
            os.environ.get('HIRER_EMBED_DOC_PREFIX', doc))


def available():
    """False if sentence-transformers isn't installed, or HIRER_DISABLE_SEMANTIC=1 (for small servers)"""
    if os.environ.get('HIRER_DISABLE_SEMANTIC') == '1':
        return False
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


_models = {}


def _embedder():
    if 'embed' not in _models:
        from sentence_transformers import SentenceTransformer
        _models['embed'] = SentenceTransformer(EMBED_MODEL)
    return _models['embed']


def _reranker():
    if 'rerank' not in _models:
        from sentence_transformers import CrossEncoder
        _models['rerank'] = CrossEncoder(RERANK_MODEL, max_length=512)
    return _models['rerank']


def candidate_chunks(candidate, n=None):
    """
    The candidate as up to n short texts: the profile (headline, summary,
    skills), then one per recent role. Scoring each piece separately means a
    long career isn't cut off at the model's input limit.
    """
    n = n or CHUNKS
    p = candidate.get('profile', {})
    head = [p.get(k) for k in ('headline', 'current_title', 'summary') if p.get(k)]
    skills = [s['name'] for s in candidate.get('skills', []) if s.get('name')]
    if skills:
        head.append('Skills: ' + ', '.join(skills))
    chunks = [' '.join(head)] if head else []
    for job in candidate.get('career_history', [])[:n - 1]:
        text = ' '.join(x for x in (job.get('title'), job.get('description')) if x)
        if text:
            chunks.append(text)
    return chunks or ['']


def candidate_text(candidate):
    return ' '.join(candidate_chunks(candidate, 3))


def _encode(texts, batch_size, progress):
    model = _embedder()
    out = []
    for i in range(0, len(texts), batch_size):
        out.append(model.encode(texts[i:i + batch_size], show_progress_bar=False,
                                normalize_embeddings=True))
        if progress:
            progress(min(i + batch_size, len(texts)), len(texts))
    return np.vstack(out).astype(np.float16)


def _cached_embeddings(texts, doc_prefix, batch_size, progress):
    key = hashlib.sha1('\x1f'.join([EMBED_MODEL, doc_prefix, *texts]).encode('utf-8')).hexdigest()[:20]
    path = CACHE_DIR / f'emb-{key}.npy'
    if path.exists():
        try:
            emb = np.load(path)
            if len(emb) == len(texts):
                path.touch()
                return emb
        except (OSError, ValueError):
            pass
    emb = _encode([doc_prefix + t for t in texts], batch_size, progress)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        np.save(path, emb)
        files = sorted(CACHE_DIR.glob('emb-*.npy'), key=lambda f: f.stat().st_mtime, reverse=True)
        for old in files[CACHE_KEEP:]:
            old.unlink(missing_ok=True)
    except OSError:
        pass        # the cache is an optimisation; ranking still works without it
    return emb


def semantic_scores(candidates, job_text, batch_size=64, progress=None):
    """best cosine similarity between the job and any piece of each candidate"""
    if not candidates:
        return np.array([])
    query_prefix, doc_prefix = _prefixes(EMBED_MODEL)
    texts, owner = [], []
    for i, c in enumerate(candidates):
        for chunk in candidate_chunks(c):
            texts.append(chunk)
            owner.append(i)
    emb = _cached_embeddings(texts, doc_prefix, batch_size, progress).astype(np.float32)
    jd = _embedder().encode([query_prefix + job_text], normalize_embeddings=True)[0]
    sims = emb @ jd
    best = np.full(len(candidates), -1.0)
    np.maximum.at(best, np.array(owner), sims)
    return best


def rerank_scores(candidates, job_query, batch_size=32):
    """cross-encoder relevance of each candidate to the job (raw model scores)"""
    pairs = [(job_query, candidate_text(c)) for c in candidates]
    return np.asarray(_reranker().predict(pairs, batch_size=batch_size, show_progress_bar=False),
                      dtype=float).reshape(len(candidates), -1)[:, -1]
