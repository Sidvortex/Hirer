import json
import gzip


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