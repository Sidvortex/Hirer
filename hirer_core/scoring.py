"""
The ranking pipeline shared by the CLI and the web backend.

    final = w_skill * S + w_semantic * E + w_behavioral * B

S  skill fit: evidence of the job's skills, experience range and title match
E  meaning match: embedding similarity between the job and the candidate
B  availability: platform activity, or the details supplied with a resume

Large candidate files are scored relative to each other (each component is
min-max normalized over the batch). Resume uploads keep absolute 0-1 scores.
A component that carries no information (semantic switched off, resumes with
no availability details) gives its weight to the others.

Optionally the top candidates are re-read by a cross-encoder, which looks at
the job and the candidate together and is more accurate than comparing two
separate embeddings.
"""

import os

import numpy as np

from . import semantic
from .features import get_features, is_resume, has_details
from .jobs import DEFAULT_JOB
from .utils import normalize_0_1, reference_date

DEFAULT_WEIGHTS = {'skill': 0.40, 'semantic': 0.35, 'behavioral': 0.25}

# how the skill composite is built from its parts
SKILL_PARTS = {'skill_score': 0.55, 'experience_score': 0.28, 'title_score': 0.17}

RERANK_TOP_K = int(os.environ.get('HIRER_RERANK_TOP_K', '200'))
RERANK_WEIGHT = float(os.environ.get('HIRER_RERANK_WEIGHT', '0.5'))


def effective_weights(weights, components, available=None, require_variation=True):
    """
    Drop the weight of any component that is unavailable, or (when scores are
    compared within the batch) doesn't vary; rescale the rest to sum to 1.
    """
    available = available or {k: True for k in weights}
    weights = dict(weights)
    # semantic and keyword scores both measure fit to the job, so when one of
    # them is unavailable its weight goes to the other, not to availability
    for a, b in (('semantic', 'skill'), ('skill', 'semantic')):
        if not available.get(a, True) and available.get(b, True):
            weights[b] = weights.get(b, 0) + weights.get(a, 0)
            weights[a] = 0.0
    informative = {k: w for k, w in weights.items()
                   if w > 0 and available.get(k, True)
                   and (not require_variation or np.ptp(components[k]) > 0)}
    total = sum(informative.values())
    if total == 0:
        return dict(weights)
    return {k: (informative.get(k, 0.0) / total) for k in weights}


def combine(components, weights):
    return sum(weights[k] * components[k] for k in weights)


def build_reasoning(candidate, feats):
    p = candidate.get('profile', {})
    sig = candidate.get('redrob_signals', {})
    parts = [f"{p.get('current_title') or 'Unknown'} with "
             f"{(p.get('years_of_experience') or 0):.1f} yrs exp",
             f"{len(feats['must_matches'])} JD skill matches"]
    if is_resume(candidate):
        # parsed from a resume: only mention availability facts someone supplied
        d = candidate.get('_details') or {}
        if d.get('notice_period_days') is not None:
            parts.append(f"{d['notice_period_days']}-day notice")
        if d.get('open_to_work'):
            parts.append('open to work')
        if d.get('location'):
            parts.append(f"based in {d['location']}")
        if d.get('willing_to_relocate'):
            parts.append('willing to relocate')
        gh = candidate.get('_github')
        if gh:
            parts.append(f"GitHub checked: {gh['public_repos']} public repos")
        return '; '.join(parts) + '.'
    if sig.get('open_to_work_flag'):
        parts.append('open to work')
    if sig.get('github_activity_score', -1) > 50:
        parts.append(f"GitHub score {sig['github_activity_score']:.0f}")
    if sig.get('recruiter_response_rate', 0) > 0.7:
        parts.append(f"high recruiter response rate ({sig['recruiter_response_rate']:.2f})")
    return '; '.join(parts) + '.'


def score(candidates, job=None, use_semantic=True, progress=None):
    """
    The three component scores for every candidate, before weighting.
    Returns {'components', 'available', 'relative', 'features', 'reference_date'}.
    """
    job = job or DEFAULT_JOB
    say = progress or (lambda step, pct: None)
    if not candidates:
        raise ValueError('No candidates to rank.')

    ref = reference_date(candidates)
    say('Computing keyword scores...', 30)
    feats = [get_features(c, ref, job) for c in candidates]
    skill = sum(w * np.array([f[k] for f in feats]) for k, w in SKILL_PARTS.items())
    behavioral = np.array([f['behavioral_score'] for f in feats])

    if use_semantic:
        say(f'Loading embedding model ({semantic.EMBED_MODEL})...', 45)
        sem = semantic.semantic_scores(
            candidates, job.text,
            progress=lambda done, total: say(f'Encoding... {done}/{total}', 50 + int(30 * done / total)))
        sem = np.clip(sem, 0, 1)
    else:
        sem = np.zeros(len(candidates))

    resumes = all(is_resume(c) for c in candidates)
    relative = not resumes
    components = {'skill': skill, 'semantic': sem, 'behavioral': behavioral}
    available = {
        'skill': bool(job.must_have),
        'semantic': bool(use_semantic),
        # resumes have availability data only where someone filled it in
        'behavioral': (not resumes) or any(has_details(c) for c in candidates),
    }
    if not available['skill'] and not available['semantic']:
        raise ValueError("No known skills were found in the job description. Add must-have skills, "
                         "or turn on semantic matching.")
    if relative:
        components = {k: normalize_0_1(v) for k, v in components.items()}
    return {'components': components, 'available': available, 'relative': relative,
            'features': feats, 'reference_date': ref}


def rank(candidates, weights=None, use_semantic=True, top_n=100, progress=None,
         job=None, use_rerank=False):
    """
    Score and rank candidates against a job (default: the built-in one).

    progress(step: str, pct: int) is called along the way if given.
    Returns a dict with 'rows' (top_n, in rank order), 'weights_used',
    'reference_date', 'relative', 'job' and 'reranked'.
    """
    job = job or DEFAULT_JOB
    weights = dict(weights or DEFAULT_WEIGHTS)
    say = progress or (lambda step, pct: None)
    use_semantic = bool(use_semantic and weights.get('semantic', 0) > 0)

    s = score(candidates, job, use_semantic, progress)
    comp, feats = s['components'], s['features']
    used = effective_weights(weights, comp, s['available'], require_variation=s['relative'])

    say('Combining weighted scores...', 85)
    final = combine(comp, used)

    # round first so the order matches the written scores, then break exact
    # ties by candidate_id ascending
    ids = np.array([c['candidate_id'] for c in candidates])
    order = np.lexsort((ids, -np.round(final, 4)))

    rerank = {}
    if use_rerank:
        k = min(len(order), max(RERANK_TOP_K, top_n))
        top = order[:k]
        say(f'Re-ranking the top {k} with {semantic.RERANK_MODEL}...', 90)
        raw = semantic.rerank_scores([candidates[i] for i in top], job.query())
        ce = normalize_0_1(raw)
        # keep the blended score inside the range the top-k already span, so
        # nobody outside the top-k can end up above someone inside it
        hi, lo = final[top].max(), final[top].min()
        final = final.copy()
        final[top] = (1 - RERANK_WEIGHT) * final[top] + RERANK_WEIGHT * (lo + ce * (hi - lo))
        rerank = {int(i): float(v) for i, v in zip(top, ce)}
        order = np.concatenate([top[np.lexsort((ids[top], -np.round(final[top], 4)))], order[k:]])

    rounded = np.round(final, 4)
    rows = []
    for r, i in enumerate(order[:top_n], start=1):
        c = candidates[i]
        row = {
            'candidate_id': c['candidate_id'],
            'rank': r,
            'score': float(rounded[i]),
            'reasoning': build_reasoning(c, feats[i]),
            'skill': round(float(comp['skill'][i]), 4),
            'semantic': round(float(comp['semantic'][i]), 4),
            'behavioral': round(float(comp['behavioral'][i]), 4),
            'matched_skills': feats[i]['must_matches'],
            'missing_skills': feats[i]['missing'],
            'name': c.get('profile', {}).get('name'),
            'source_file': c.get('_source_file'),
        }
        if i in rerank:
            row['rerank'] = round(rerank[int(i)], 4)
        rows.append(row)

    return {'rows': rows,
            'weights_used': {k: round(v, 4) for k, v in used.items()},
            'reference_date': s['reference_date'].isoformat(),
            'relative': s['relative'],
            'reranked': bool(rerank),
            'job': job.to_dict(),
            'total_candidates': len(candidates)}
