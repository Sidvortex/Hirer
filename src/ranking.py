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
from feature_engineering import get_features, MUST_HAVE_SKILLS, _get_full_text


def build_reasoning(candidate, final_score):
    p = candidate['profile']
    sig = candidate['redrob_signals']

    title = p.get('current_title', 'Unknown')
    yoe = p.get('years_of_experience', 0)

    text = _get_full_text(candidate).lower()
    skill_hits = sum(1 for kw in MUST_HAVE_SKILLS if kw in text)

    rr = sig.get('recruiter_response_rate', 0)
    otw = sig.get('open_to_work_flag', False)
    gh = sig.get('github_activity_score', -1)

    parts = [f"{title} with {yoe:.1f} yrs exp"]
    parts.append(f"{skill_hits} JD skill matches")

    if otw:
        parts.append("open to work")
    if gh > 50:
        parts.append(f"GitHub score {gh:.0f}")
    if rr > 0.7:
        parts.append(f"high recruiter response rate ({rr:.2f})")

    return '; '.join(parts) + '.'


def rank_candidates(candidates_path, output_path, top_n=100):
    print(f"Loading candidates from {candidates_path}...")
    candidates = load_candidates(candidates_path)
    print(f"Loaded {len(candidates)} candidates")

    print("Computing feature scores...")
    feature_rows = []
    for c in tqdm(candidates, desc="Features"):
        feature_rows.append(get_features(c))

    feat_df = pd.DataFrame(feature_rows)

    # combine skill + experience + title + education
    combined_skill = (
        feat_df['skill_score'] * 0.5 +
        feat_df['experience_score'] * 0.25 +
        feat_df['title_score'] * 0.15 +
        feat_df['education_score'] * 0.10
    )

    behavioral_arr = feat_df['behavioral_score'].values

    final_scores = (
        normalize_0_1(combined_skill.values) * 0.60 +
        normalize_0_1(behavioral_arr) * 0.40
    )

    sorted_idx = np.argsort(-final_scores)
    top_idx = sorted_idx[:top_n]

    rows = []
    for rank, idx in enumerate(top_idx, start=1):
        c = candidates[idx]
        reasoning = build_reasoning(c, final_scores[idx])
        rows.append({
            'candidate_id': c['candidate_id'],
            'rank': rank,
            'score': round(final_scores[idx], 4),
            'reasoning': reasoning
        })

    out_df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    out_df.to_csv(output_path, index=False)
    print(f"Done. Wrote to {output_path}")
    print(f"Top candidate: {rows[0]['candidate_id']} (score={rows[0]['score']})")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidates', required=True)
    parser.add_argument('--out', default='output/submission.csv')
    parser.add_argument('--top-n', type=int, default=100)
    args = parser.parse_args()

    rank_candidates(args.candidates, args.out, top_n=args.top_n)