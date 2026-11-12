"""
Command-line ranker.

Usage (from the repo root):
    python scripts/rank.py --candidates data/candidates_small.jsonl
    python scripts/rank.py --candidates data/candidates.jsonl.gz --no-semantic
    python scripts/rank.py --candidates data/candidates_small.jsonl --job my_job.txt --rerank

The scoring itself lives in hirer_core/, which the web backend uses too.
"""

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from hirer_core import rank, get_job, DEFAULT_WEIGHTS      # noqa: E402
from hirer_core.utils import load_candidates               # noqa: E402

CSV_COLUMNS = ['candidate_id', 'rank', 'score', 'reasoning']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidates', required=True, help='path to candidates.jsonl or .jsonl.gz')
    ap.add_argument('--out', default='output/submission.csv')
    ap.add_argument('--top-n', type=int, default=100)
    ap.add_argument('--job', help='text file with a job description (default: the built-in Senior AI Engineer role)')
    ap.add_argument('--preset', type=int, help='id of a built-in job (1-20)')
    ap.add_argument('--no-semantic', action='store_true', help='skip semantic scoring (faster)')
    ap.add_argument('--rerank', action='store_true', help='re-read the top candidates with a cross-encoder')
    args = ap.parse_args()

    job = get_job(preset=args.preset, text=open(args.job, encoding='utf-8').read() if args.job else None)
    print(f'Job: {job.title} ({len(job.must_have)} must-have skills)')
    print(f'Loading candidates from {args.candidates}...')
    candidates = load_candidates(args.candidates)
    print(f'Loaded {len(candidates):,} candidates')

    result = rank(candidates, DEFAULT_WEIGHTS, use_semantic=not args.no_semantic, top_n=args.top_n,
                  job=job, use_rerank=args.rerank, progress=lambda step, pct: print(step))
    rows = result['rows']

    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    with open(args.out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)

    print(f"\nRecency measured from {result['reference_date']}")
    print('Weights used: ' + ', '.join(f'{k} {v:.2f}' for k, v in result['weights_used'].items()))
    print(f'Wrote {len(rows)} candidates to {args.out}')
    print(f"Top candidate: {rows[0]['candidate_id']} (score={rows[0]['score']:.4f})")
    print(f"Reasoning: {rows[0]['reasoning']}")


if __name__ == '__main__':
    main()
