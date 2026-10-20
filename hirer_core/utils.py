import gzip
import json
import re
from datetime import date, datetime
from functools import lru_cache

import numpy as np


def load_candidates(path):
    """load from .jsonl or .jsonl.gz"""
    opener = gzip.open(path, 'rt', encoding='utf-8') if str(path).endswith('.gz') \
        else open(path, 'r', encoding='utf-8')
    candidates = []
    with opener as f:
        for line in f:
            line = line.strip()
            if line:
                candidates.append(json.loads(line))
    return candidates


def parse_date(date_str):
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def days_since(date_str, ref_date=None):
    """days between a 'YYYY-MM-DD' string and ref_date (default: today)"""
    ref_date = ref_date or date.today()
    d = parse_date(date_str)
    if d is None:
        return 365  # unknown date counts as a year ago
    return (ref_date - d).days


def reference_date(candidates):
    """
    The date that recency is measured from: the newest last_active_date in
    the batch. Using today's date instead would make every candidate look
    inactive once the data is a few months old, and results would change
    depending on the day you ran them.
    """
    dates = [parse_date(c.get('redrob_signals', {}).get('last_active_date'))
             for c in candidates]
    dates = [d for d in dates if d is not None]
    return max(dates) if dates else date.today()


def normalize_0_1(arr):
    """min-max normalize to 0-1; a constant array becomes all zeros"""
    arr = np.asarray(arr, dtype=float)
    mn, mx = arr.min(), arr.max()
    if mx == mn:
        return np.zeros_like(arr)
    return (arr - mn) / (mx - mn)


@lru_cache(maxsize=None)
def _term_pattern(term):
    # whole-word match with an optional plural, so 'llm' matches 'LLMs'
    # but 'cv' does not match 'OpenCV' and 'ui' does not match 'building'
    return re.compile(r'(?<![a-z0-9])' + re.escape(term) + r'(?:s|es)?(?![a-z0-9])')


def contains_term(text, term):
    """text must already be lowercase"""
    return _term_pattern(term).search(text) is not None


def matched_terms(text, terms):
    return [t for t in terms if contains_term(text, t)]


def build_candidate_text(candidate):
    """text blob used for semantic matching"""
    parts = []
    p = candidate.get('profile', {})
    for key in ('headline', 'summary', 'current_title'):
        if p.get(key):
            parts.append(p[key])

    skills = [s['name'] for s in candidate.get('skills', [])]
    if skills:
        parts.append('Skills: ' + ', '.join(skills))

    for job in candidate.get('career_history', [])[:2]:
        if job.get('title'):
            parts.append(job['title'])
        if job.get('description'):
            parts.append(job['description'][:300])

    return ' '.join(parts)
