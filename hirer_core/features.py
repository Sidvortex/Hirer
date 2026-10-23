"""Per-candidate feature scores, each in the range 0-1."""

from .jd import MUST_HAVE_SKILLS, NICE_TO_HAVE, NEGATIVE_SIGNALS, GOOD_TITLES
from .utils import contains_term, matched_terms, days_since


def full_text(candidate):
    """all candidate text used for keyword search, lowercased"""
    p = candidate.get('profile', {})
    parts = [p.get('headline', ''), p.get('summary', ''), p.get('current_title', '')]
    for job in candidate.get('career_history', []):
        parts += [job.get('title', ''), job.get('description', '')]
    parts += [s.get('name', '') for s in candidate.get('skills', [])]
    parts += [c.get('name', '') for c in candidate.get('certifications', [])]
    return ' '.join(x for x in parts if x).lower()


def skill_matches(candidate, text=None):
    text = text if text is not None else full_text(candidate)
    return {
        'must': matched_terms(text, MUST_HAVE_SKILLS),
        'nice': matched_terms(text, NICE_TO_HAVE),
        'negative': matched_terms(text, NEGATIVE_SIGNALS),
    }


def skill_score(candidate, matches=None):
    """keyword overlap with the must-have and nice-to-have lists"""
    m = matches or skill_matches(candidate)
    score = (len(m['must']) * 2 + len(m['nice']) * 0.5) / (len(MUST_HAVE_SKILLS) * 2)
    score = min(score, 1.0)
    if m['negative']:
        # soft penalty, never below 60% of the score
        score *= max(0.6, 1 - 0.1 * len(m['negative']))
    return score


def experience_score(candidate):
    """fit to the 5-9 year target range"""
    yoe = candidate.get('profile', {}).get('years_of_experience', 0) or 0
    if 5 <= yoe <= 9:
        return 1.0
    if 4 <= yoe < 5:
        return 0.8
    if 9 < yoe <= 12:
        return 0.75
    if 3 <= yoe < 4:
        return 0.5
    if yoe > 12:
        return 0.6
    return 0.2


def title_score(candidate):
    title = (candidate.get('profile', {}).get('current_title') or '').lower()
    if any(contains_term(title, t) for t in GOOD_TITLES):
        return 1.0
    if contains_term(title, 'engineer') or contains_term(title, 'scientist'):
        return 0.6
    if contains_term(title, 'developer') or contains_term(title, 'analyst'):
        return 0.3
    return 0.1


TIER_MAP = {'tier_1': 1.0, 'tier_2': 0.75, 'tier_3': 0.5, 'tier_4': 0.3, 'unknown': 0.4}


def education_score(candidate):
    edu = candidate.get('education', [])
    if not edu:
        return 0.4
    return max(TIER_MAP.get(e.get('tier', 'unknown'), 0.4) for e in edu)


def behavioral_score(candidate, ref_date=None):
    """
    engagement / availability from redrob_signals.
    ref_date is the date recency is measured from (see utils.reference_date).
    """
    sig = candidate.get('redrob_signals', {})
    parts = []

    days_inactive = days_since(sig.get('last_active_date'), ref_date)
    activity = 1.0 if days_inactive <= 7 else 0.8 if days_inactive <= 30 \
        else 0.5 if days_inactive <= 90 else 0.1
    parts.append((activity, 0.25))

    parts.append((1.0 if sig.get('open_to_work_flag', False) else 0.3, 0.20))
    parts.append((sig.get('recruiter_response_rate', 0.5), 0.20))

    rt = sig.get('avg_response_time_hours', 48)
    rt_score = 1.0 if rt <= 2 else 0.8 if rt <= 12 else 0.6 if rt <= 24 else 0.3 if rt <= 72 else 0.1
    parts.append((rt_score, 0.10))

    gh = sig.get('github_activity_score', -1)
    parts.append((0.3 if gh == -1 else gh / 100.0, 0.15))

    parts.append((sig.get('profile_completeness_score', 50) / 100.0, 0.05))

    notice = sig.get('notice_period_days', 60)
    np_score = 1.0 if notice <= 30 else 0.7 if notice <= 60 else 0.4 if notice <= 90 else 0.2
    parts.append((np_score, 0.05))

    return sum(s * w for s, w in parts) / sum(w for _, w in parts)


def get_features(candidate, ref_date=None):
    text = full_text(candidate)
    matches = skill_matches(candidate, text)
    return {
        'candidate_id': candidate['candidate_id'],
        'skill_score': skill_score(candidate, matches),
        'experience_score': experience_score(candidate),
        'title_score': title_score(candidate),
        'education_score': education_score(candidate),
        'behavioral_score': behavioral_score(candidate, ref_date),
        'must_matches': matches['must'],
        'negative_matches': matches['negative'],
    }
