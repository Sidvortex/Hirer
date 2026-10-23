"""
Command-line ranker.

Usage (from the repo root):
    python src/ranking.py --candidates data/candidates.jsonl --out output/submission.csv
    python src/ranking.py --candidates data/candidates.jsonl.gz --no-semantic

The scoring itself lives in hirer_core/, which the web backend uses too.
"""

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from hirer_core import rank, DEFAULT_WEIGHTS          # noqa: E402
from hirer_core.utils import load_candidates          # noqa: E402

CSV_COLUMNS = ['candidate_id', 'rank', 'score', 'reasoning']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidates', required=True, help='path to candidates.jsonl or .jsonl.gz')
    ap.add_argument('--out', default='output/submission.csv')
    ap.add_argument('--top-n', type=int, default=100)
    ap.add_argument('--no-semantic', action='store_true', help='skip semantic scoring (faster)')
    args = ap.parse_args()

    print(f'Loading candidates from {args.candidates}...')
    candidates = load_candidates(args.candidates)
    print(f'Loaded {len(candidates):,} candidates')

    result = rank(candidates, DEFAULT_WEIGHTS, use_semantic=not args.no_semantic,
                  top_n=args.top_n, progress=lambda step, pct: print(step))
    rows = result['rows']

    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    pd.DataFrame(rows)[CSV_COLUMNS].to_csv(args.out, index=False)

    print(f"\nRecency measured from {result['reference_date']}")
    print('Weights used: ' + ', '.join(f'{k} {v:.2f}' for k, v in result['weights_used'].items()))
    print(f'Wrote {len(rows)} candidates to {args.out}')
    print(f"Top candidate: {rows[0]['candidate_id']} (score={rows[0]['score']:.4f})")
    print(f"Reasoning: {rows[0]['reasoning']}")


if __name__ == '__main__':
    main()
