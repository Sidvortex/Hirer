"""
ranking pipeline
"""

import argparse
import sys
import os
import numpy as np
import pandas as pd
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(__file__))
from utils import load_candidates, normalize_0_1
from feature_engineering import get_features


def rank_candidates(candidates_path, output_path, top_n=100):
    print(f"Loading candidates from {candidates_path}...")
    candidates = load_candidates(candidates_path)
    print(f"Loaded {len(candidates)} candidates")

    print("Computing feature scores...")
    feature_rows = []
    for c in tqdm(candidates, desc="Features"):
        feature_rows.append(get_features(c))

    feat_df = pd.DataFrame(feature_rows)

    # combine scores
    # TODO: add semantic and behavioral later
    final_scores = (
        feat_df['skill_score'] * 0.5 +
        feat_df['experience_score'] * 0.25 +
        feat_df['title_score'] * 0.15 +
        feat_df['education_score'] * 0.10
    )

    sorted_idx = np.argsort(-final_scores.values)
    top_idx = sorted_idx[:top_n]

    rows = []
    for rank, idx in enumerate(top_idx, start=1):
        c = candidates[idx]
        rows.append({
            'candidate_id': c['candidate_id'],
            'rank': rank,
            'score': round(final_scores.iloc[idx], 4),
            'reasoning': f"{c['profile']['current_title']} with {c['profile']['years_of_experience']} yrs exp."
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