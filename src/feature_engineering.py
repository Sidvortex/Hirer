import numpy as np
from utils import days_since


# keywords from the JD
MUST_HAVE_SKILLS = [
    'embeddings', 'sentence-transformers',
    'vector database', 'vector search', 'faiss', 'pinecone',
    'python', 'ranking', 'retrieval', 'nlp', 'llm',
    'ndcg', 'mrr', 'semantic search', 'transformer'
]

NICE_TO_HAVE = [
    'lora', 'qlora', 'pytorch', 'tensorflow',
    'hugging face', 'xgboost', 'a/b testing'
]

NEGATIVE_SIGNALS = [
    'computer vision', 'image classification',
    'object detection', 'speech recognition', 'robotics'
]

GOOD_TITLES = [
    'ml engineer', 'machine learning engineer', 'ai engineer',
    'nlp engineer', 'search engineer', 'data scientist',
    'senior engineer', 'research engineer'
]


def skill_score(candidate):
    all_text = _get_full_text(candidate).lower()

    must_matches = sum(1 for kw in MUST_HAVE_SKILLS if kw in all_text)
    nice_matches = sum(1 for kw in NICE_TO_HAVE if kw in all_text)
    neg_matches = sum(1 for kw in NEGATIVE_SIGNALS if kw in all_text)

    score = (must_matches * 2 + nice_matches * 0.5) / (len(MUST_HAVE_SKILLS) * 2)
    score = min(score, 1.0)

    if neg_matches > 0:
        score *= max(0.5, 1 - 0.15 * neg_matches)

    return score


def experience_score(candidate):
    yoe = candidate.get('profile', {}).get('years_of_experience', 0)

    if 5 <= yoe <= 9:
        return 1.0
    elif 4 <= yoe < 5:
        return 0.8
    elif 9 < yoe <= 12:
        return 0.75
    elif 3 <= yoe < 4:
        return 0.5
    elif yoe > 12:
        return 0.6
    else:
        return 0.2


def title_score(candidate):
    title = candidate.get('profile', {}).get('current_title', '').lower()
    for t in GOOD_TITLES:
        if t in title:
            return 1.0
    if 'engineer' in title or 'scientist' in title:
        return 0.6
    if 'developer' in title or 'analyst' in title:
        return 0.3
    return 0.1


def education_score(candidate):
    tier_map = {'tier_1': 1.0, 'tier_2': 0.75, 'tier_3': 0.5, 'tier_4': 0.3, 'unknown': 0.4}

    edu = candidate.get('education', [])
    if not edu:
        return 0.4

    best = 0.0
    for e in edu:
        t = e.get('tier', 'unknown')
        best = max(best, tier_map.get(t, 0.4))
    return best


def behavioral_score(candidate):
    sig = candidate.get('redrob_signals', {})
    scores = []

    # activity recency
    days_inactive = days_since(sig.get('last_active_date', '2020-01-01'))
    if days_inactive <= 7:
        activity = 1.0
    elif days_inactive <= 30:
        activity = 0.8
    elif days_inactive <= 90:
        activity = 0.5
    else:
        activity = 0.1
    scores.append(('activity', activity, 0.25))

    # open to work
    otw = 1.0 if sig.get('open_to_work_flag', False) else 0.3
    scores.append(('open_to_work', otw, 0.2))

    # recruiter response rate
    rr = sig.get('recruiter_response_rate', 0.5)
    scores.append(('response_rate', rr, 0.2))

    # github score
    gh = sig.get('github_activity_score', -1)
    if gh == -1:
        gh_score = 0.3
    else:
        gh_score = gh / 100.0
    scores.append(('github', gh_score, 0.15))

    # notice period
    np_days = sig.get('notice_period_days', 60)
    if np_days <= 30:
        np_score = 1.0
    elif np_days <= 60:
        np_score = 0.7
    elif np_days <= 90:
        np_score = 0.4
    else:
        np_score = 0.2
    scores.append(('notice', np_score, 0.1))

    # response time
    avg_rt = sig.get('avg_response_time_hours', 48)
    if avg_rt <= 2:
        rt_score = 1.0
    elif avg_rt <= 12:
        rt_score = 0.8
    elif avg_rt <= 24:
        rt_score = 0.6
    elif avg_rt <= 72:
        rt_score = 0.3
    else:
        rt_score = 0.1
    scores.append(('response_time', rt_score, 0.1))

    total = sum(s * w for _, s, w in scores)
    total_weight = sum(w for _, _, w in scores)
    return total / total_weight


def get_features(candidate):
    return {
        'candidate_id': candidate['candidate_id'],
        'skill_score': skill_score(candidate),
        'experience_score': experience_score(candidate),
        'title_score': title_score(candidate),
        'education_score': education_score(candidate),
        'behavioral_score': behavioral_score(candidate),
    }


def _get_full_text(candidate):
    parts = []
    p = candidate.get('profile', {})
    parts.append(p.get('headline', ''))
    parts.append(p.get('summary', ''))
    parts.append(p.get('current_title', ''))

    for job in candidate.get('career_history', []):
        parts.append(job.get('title', ''))
        parts.append(job.get('description', ''))

    for skill in candidate.get('skills', []):
        parts.append(skill.get('name', ''))

    for cert in candidate.get('certifications', []):
        parts.append(cert.get('name', ''))

    return ' '.join(parts)