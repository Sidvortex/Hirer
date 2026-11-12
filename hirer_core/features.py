"""Per-candidate feature scores, each in the range 0-1, measured against a Job."""

import re

from .jobs import DEFAULT_JOB
from .skills import term_in
from .utils import contains_term, days_since

# How much a skill mention counts, by where it appears. Work described in a
# job counts fully; a bare entry in the skills list counts by stated
# proficiency; a mention only in the headline or summary counts least.
CAREER, ABOUT = 1.0, 0.6
PROFICIENCY = {'expert': 1.0, 'advanced': 1.0, 'intermediate': 0.8, 'beginner': 0.6}


def text_parts(candidate):
    p = candidate.get('profile', {})
    career = ' '.join(f"{j.get('title') or ''} {j.get('description') or ''}"
                      for j in candidate.get('career_history', []))
    about = ' '.join(p.get(k) or '' for k in ('headline', 'summary', 'current_title'))
    return {'career': career.lower(), 'about': about.lower()}


def full_text(candidate):
    """all candidate text used for keyword search, lowercased"""
    parts = text_parts(candidate)
    listed = ' '.join((x.get('name') or '') for x in
                      candidate.get('skills', []) + candidate.get('certifications', []))
    return f"{parts['about']} {parts['career']} {listed}".lower()


def skill_evidence(candidate, terms, parts=None):
    """{skill: strength 0-1} for every term the candidate shows evidence of"""
    parts = parts or text_parts(candidate)
    listed = [((s.get('name') or '').lower(), PROFICIENCY.get(s.get('proficiency'), 0.8))
              for s in candidate.get('skills', [])]
    listed += [((c.get('name') or '').lower(), 0.8) for c in candidate.get('certifications', [])]
    tested = {k.lower(): v / 100.0 for k, v in
              (candidate.get('redrob_signals', {}).get('skill_assessment_scores') or {}).items()}
    found = {}
    for term in terms:
        claimed = 0.0
        if term_in(parts['career'], term):
            claimed = CAREER
        else:
            claimed = max([w for name, w in listed if term_in(name, term)], default=0.0)
            if not claimed and term_in(parts['about'], term):
                claimed = ABOUT
        # a platform skill test is the only checked signal, so it counts as much as the claim
        scores = [v for name, v in tested.items() if term_in(name, term)]
        strength = (claimed + max(scores)) / 2 if scores else claimed
        if strength > 0:
            found[term] = round(strength, 3)
    return found


def skill_matches(candidate, job=DEFAULT_JOB, parts=None):
    parts = parts or text_parts(candidate)
    text = full_text(candidate)
    return {
        'must': skill_evidence(candidate, job.must_have, parts),
        'nice': skill_evidence(candidate, job.nice_to_have, parts),
        'negative': [t for t in job.negative if term_in(text, t)],
    }


def skill_score(candidate, job=DEFAULT_JOB, matches=None):
    """evidence of the job's must-have and nice-to-have skills"""
    if not job.must_have:
        return 0.0
    m = matches or skill_matches(candidate, job)
    score = (sum(m['must'].values()) * 2 + sum(m['nice'].values()) * 0.5) / (len(job.must_have) * 2)
    score = min(score, 1.0)
    if m['negative']:
        # soft penalty, never below 60% of the score
        score *= max(0.6, 1 - 0.1 * len(m['negative']))
    return score


def experience_score(candidate, job=DEFAULT_JOB):
    """fit to the job's experience range; neutral when the job doesn't give one"""
    if not job.years:
        return 0.5
    yoe = candidate.get('profile', {}).get('years_of_experience', 0) or 0
    lo, hi = job.years
    if yoe >= lo and (hi is None or yoe <= hi):
        return 1.0
    if lo - 1 <= yoe < lo:
        return 0.8
    if lo - 2 <= yoe < lo - 1:
        return 0.5
    if yoe < lo:
        return 0.2
    return 0.75 if yoe <= hi + 3 else 0.6


_LEVELS = {'senior', 'junior', 'lead', 'staff', 'principal', 'sr', 'jr', 'associate', 'i', 'ii', 'iii'}


def title_score(candidate, job=DEFAULT_JOB):
    title = (candidate.get('profile', {}).get('current_title') or '').lower()
    if any(contains_term(title, t) for t in job.good_titles):
        return 1.0
    if job is DEFAULT_JOB:
        if contains_term(title, 'engineer') or contains_term(title, 'scientist'):
            return 0.6
        if contains_term(title, 'developer') or contains_term(title, 'analyst'):
            return 0.3
        return 0.1
    # other jobs: share of the job title's words that the candidate's title has
    words = [w for w in re.findall(r'[a-z+#.]+', job.title.lower()) if w not in _LEVELS]
    if not words:
        return 0.5
    return 0.1 + 0.9 * sum(contains_term(title, w) for w in words) / len(words)


def location_fit(location, willing_to_relocate, job):
    """1.0 in one of the job's locations, lower if a move is needed; None if the job names no location"""
    if not job.locations:
        return None
    loc = (location or '').lower()
    if 'remote' in job.locations or any(contains_term(loc, t) for t in job.locations):
        return 1.0
    if willing_to_relocate is True:
        return 0.8
    if willing_to_relocate is False and loc:
        return 0.2
    return 0.5


def behavioral_score(candidate, ref_date=None, job=DEFAULT_JOB):
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

    loc = location_fit(candidate.get('profile', {}).get('location'), sig.get('willing_to_relocate'), job)
    if loc is not None:
        parts.append((loc, 0.10))

    if sig.get('interview_completion_rate') is not None:
        parts.append((sig['interview_completion_rate'], 0.05))

    return sum(s * w for s, w in parts) / sum(w for _, w in parts)


# ── resume candidates ────────────────────────────────────────────────────────
# A resume has no platform activity data. The recruiter (or a detail file in
# the ZIP) can supply a few availability facts instead; those go in
# candidate["_details"]. Anything not supplied counts as neutral (0.5), so a
# candidate isn't punished for a blank field.

DETAIL_FIELDS = ('notice_period_days', 'open_to_work', 'willing_to_relocate', 'location')


def is_resume(candidate):
    return bool(candidate.get('_source_file'))


def has_details(candidate):
    d = candidate.get('_details') or {}
    return any(d.get(k) not in (None, '') for k in DETAIL_FIELDS)


def availability_score(candidate, job=DEFAULT_JOB):
    d = candidate.get('_details') or {}
    parts = []

    notice = d.get('notice_period_days')
    if notice is None:
        parts.append((0.5, 0.4))
    else:
        parts.append((1.0 if notice <= 30 else 0.7 if notice <= 60 else 0.4 if notice <= 90 else 0.2, 0.4))

    otw = d.get('open_to_work')
    parts.append((0.5 if otw is None else 1.0 if otw else 0.3, 0.3))

    where = d.get('location') or candidate.get('profile', {}).get('location')
    loc = location_fit(where, d.get('willing_to_relocate'), job)
    parts.append((0.5 if loc is None else loc, 0.3))

    return sum(s * w for s, w in parts) / sum(w for _, w in parts)


def get_features(candidate, ref_date=None, job=DEFAULT_JOB):
    matches = skill_matches(candidate, job)
    return {
        'candidate_id': candidate['candidate_id'],
        'skill_score': skill_score(candidate, job, matches),
        'experience_score': experience_score(candidate, job),
        'title_score': title_score(candidate, job),
        'behavioral_score': availability_score(candidate, job) if is_resume(candidate)
                            else behavioral_score(candidate, ref_date, job),
        'must_matches': list(matches['must']),
        'missing': [t for t in job.must_have if t not in matches['must']],
        'negative_matches': matches['negative'],
    }
