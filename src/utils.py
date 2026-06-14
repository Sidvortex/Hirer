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
        return 365


def normalize_0_1(arr):
    """min-max normalize to 0-1"""
    arr = np.array(arr, dtype=float)
    mn, mx = arr.min(), arr.max()
    if mx == mn:
        return np.zeros_like(arr)
    return (arr - mn) / (mx - mn)