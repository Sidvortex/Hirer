import json
import gzip
from datetime import datetime, date
import numpy as np


def load_candidates(path):
    """load from .jsonl or .jsonl.gz"""
    candidates = []
    if path.endswith('.gz'):
        opener = gzip.open(path, 'rt', encoding='utf-8')
    else:
        opener = open(path, 'r', encoding='utf-8')
    
    with opener as f:
        for line in f:
            line = line.strip()
            if line:
                candidates.append(json.loads(line))
    return candidates


def days_since(date_str, ref_date=None):
    """how many days since a date string like '2024-03-15'"""
    if ref_date is None:
        ref_date = date.today()
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
        return (ref_date - d).days
    except:
        return 365  # default to 1 year if parse fails


def normalize_0_1(arr):
    """min-max normalize to 0-1"""
    arr = np.array(arr, dtype=float)
    mn, mx = arr.min(), arr.max()
    if mx == mn:
        return np.zeros_like(arr)
    return (arr - mn) / (mx - mn)


def get_all_skill_names(candidate):
    """flatten skill names from a candidate"""
    return [s['name'].lower() for s in candidate.get('skills', [])]


def build_candidate_text(candidate):
    """make a text blob for semantic matching"""
    parts = []
    
    p = candidate.get('profile', {})
    if p.get('headline'):
        parts.append(p['headline'])
    if p.get('summary'):
        parts.append(p['summary'])
    if p.get('current_title'):
        parts.append(p['current_title'])
    
    # add skills
    skills = [s['name'] for s in candidate.get('skills', [])]
    if skills:
        parts.append('Skills: ' + ', '.join(skills))
    
    # career descriptions (first 2 roles)
    for job in candidate.get('career_history', [])[:2]:
        if job.get('title'):
            parts.append(job['title'])
        if job.get('description'):
            parts.append(job['description'][:300])
    
    return ' '.join(parts)
