"""
ranking pipeline
"""

import argparse
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_candidates


def rank_candidates(candidates_path, output_path, top_n=100):
    print(f"Loading candidates from {candidates_path}...")
    candidates = load_candidates(candidates_path)
    print(f"Loaded {len(candidates)} candidates")

    # TODO: add scoring here
    # for now just return first N
    rows = []
    for i, c in enumerate(candidates[:top_n]):
        rows.append({
            'candidate_id': c['candidate_id'],
            'rank': i + 1,
            'score': 0.0,
            'reasoning': 'placeholder'
        })

    out_df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    out_df.to_csv(output_path, index=False)
    print(f"Done. Wrote to {output_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidates', required=True)
    parser.add_argument('--out', default='output/submission.csv')
    parser.add_argument('--top-n', type=int, default=100)
    args = parser.parse_args()

    rank_candidates(args.candidates, args.out, top_n=args.top_n)