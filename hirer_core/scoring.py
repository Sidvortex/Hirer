"""
The ranking pipeline shared by the CLI and the web backend.

final = w_skill * N(S) + w_semantic * N(E) + w_behavioral * N(B)

where N is min-max normalization over the batch. A component that is the
same for every candidate (for example behavioral signals in resume uploads,
where no platform data exists, or semantic scores when semantic matching is
switched off) carries no information, so its weight is handed to the other
components instead of being silently wasted.
"""

import numpy as np

from .features import get_features
from .jd import JD_TEXT
from .utils import normalize_0_1, build_candidate_text, reference_date

DEFAULT_WEIGHTS = {'skill': 0.40, 'semantic': 0.35, 'behavioral': 0.25}

# how the skill composite is built from its parts
SKILL_PARTS = {'skill_score': 0.50, 'experience_score': 0.25,
               'title_score': 0.15, 'education_score': 0.10}

_MODEL = None


def _model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    return _MODEL


def semantic_scores(candidates, batch_size=64, progress=None):
    """cosine similarity between each candidate's text and the job description"""
    model = _model()
    jd = model.encode([JD_TEXT], normalize_embeddings=True)[0]
    texts = [build_candidate_text(c) for c in candidates]
    out = []
    for i in range(0, len(texts), batch_size):
        emb = model.encode(texts[i:i + batch_size], show_progress_bar=False,
                           normalize_embeddings=True)
        out.append(emb @ jd)
        if progress:
            progress(min(i + batch_size, len(texts)), len(texts))
    return np.concatenate(out) if out else np.array([])


def effective_weights(weights, components):
    """drop the weight of any component that doesn't vary, rescale the rest"""
    informative = {k: w for k, w in weights.items()
                   if w > 0 and np.ptp(components[k]) > 0}
    total = sum(informative.values())
    if total == 0:
        return dict(weights)
    return {k: (informative.get(k, 0.0) / total) for k in weights}


def build_reasoning(candidate, feats):
    p = candidate.get('profile', {})
    sig = candidate.get('redrob_signals', {})
    parts = [f"{p.get('current_title') or 'Unknown'} with "
             f"{(p.get('years_of_experience') or 0):.1f} yrs exp",
             f"{len(feats['must_matches'])} JD skill matches"]
    if candidate.get('_source_file'):
        # parsed from a resume: the activity signals are placeholders, not facts
        return '; '.join(parts) + '.'
    if sig.get('open_to_work_flag'):
        parts.append('open to work')
    if sig.get('github_activity_score', -1) > 50:
        parts.append(f"GitHub score {sig['github_activity_score']:.0f}")
    if sig.get('recruiter_response_rate', 0) > 0.7:
        parts.append(f"high recruiter response rate ({sig['recruiter_response_rate']:.2f})")
    return '; '.join(parts) + '.'


def rank(candidates, weights=None, use_semantic=True, top_n=100, progress=None):
    """
    Score and rank candidates.

    progress(step: str, pct: int) is called along the way if given.
    Returns a dict with 'rows' (top_n, in rank order), 'weights_used' and
    'reference_date'.
    """
    weights = dict(weights or DEFAULT_WEIGHTS)
    say = progress or (lambda step, pct: None)
    if not candidates:
        raise ValueError('No candidates to rank.')

    ref = reference_date(candidates)
    say('Computing keyword scores...', 30)
    feats = [get_features(c, ref) for c in candidates]

    skill = sum(w * np.array([f[k] for f in feats]) for k, w in SKILL_PARTS.items())
    behavioral = np.array([f['behavioral_score'] for f in feats])

    if use_semantic and weights.get('semantic', 0) > 0:
        say('Loading sentence-transformer model...', 50)
        semantic = semantic_scores(
            candidates,
            progress=lambda done, total: say(f'Encoding... {done}/{total}',
                                             50 + int(30 * done / total)))
    else:
        semantic = np.zeros(len(candidates))  # constant, so its weight is reassigned

    components = {'skill': skill, 'semantic': semantic, 'behavioral': behavioral}
    used = effective_weights(weights, components)
    normed = {k: normalize_0_1(v) for k, v in components.items()}

    say('Combining weighted scores...', 85)
    final = sum(used[k] * normed[k] for k in used)

    # round first so the order matches the written scores, then break exact
    # ties by candidate_id ascending
    rounded = np.round(final, 4)
    ids = np.array([c['candidate_id'] for c in candidates])
    order = np.lexsort((ids, -rounded))[:top_n]

    rows = []
    for r, i in enumerate(order, start=1):
        c = candidates[i]
        rows.append({
            'candidate_id': c['candidate_id'],
            'rank': r,
            'score': float(rounded[i]),
            'reasoning': build_reasoning(c, feats[i]),
            'skill': round(float(normed['skill'][i]), 4),
            'semantic': round(float(normed['semantic'][i]), 4),
            'behavioral': round(float(normed['behavioral'][i]), 4),
            'matched_skills': feats[i]['must_matches'],
            'name': c.get('profile', {}).get('name'),
            'source_file': c.get('_source_file'),
        })

    return {'rows': rows,
            'weights_used': {k: round(v, 4) for k, v in used.items()},
            'reference_date': ref.isoformat(),
            'total_candidates': len(candidates)}
