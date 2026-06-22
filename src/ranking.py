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
from utils import load_candidates, normalize_0_1, build_candidate_text
from feature_engineering import get_features, MUST_HAVE_SKILLS, _get_full_text


# the job description text for semantic matching
JD_TEXT = """
Senior AI Engineer founding team role at Redrob AI.
Requirements: Production experience with embeddings-based retrieval systems using sentence-transformers,
OpenAI embeddings, BGE, E5 or similar. Vector databases and hybrid search infrastructure:
Pinecone, Weaviate, Qdrant, Milvus, OpenSearch, Elasticsearch, FAISS.
Strong Python. Evaluation frameworks for ranking systems: NDCG, MRR, MAP, A/B testing.
NLP, information retrieval, semantic search, LLM fine-tuning, learning to rank.
5-9 years experience. Location: Pune or Noida India, willing to relocate.
"""

# trying sentence transformers now - Ishan suggested this
def compute_semantic_scores(candidates, batch_size=64):
    try:
        from sentence_transformers import SentenceTransformer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        print("sentence-transformers not installed, skipping")
        return [0.5] * len(candidates)

    print("Loading sentence transformer model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    jd_embedding = model.encode([JD_TEXT])

    print(f"Encoding {len(candidates)} candidates...")
    texts = [build_candidate_text(c) for c in candidates]

    embeddings = []
    for i in tqdm(range(0, len(texts), batch_size), desc="Encoding"):
        batch = texts[i:i+batch_size]
        emb = model.encode(batch, show_progress_bar=False)
        embeddings.append(emb)

    all_embeddings = np.vstack(embeddings)
    sims = cosine_similarity(jd_embedding, all_embeddings)[0]
    return sims.tolist()


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


def rank_candidates(candidates_path, output_path, top_n=100, use_semantic=True):
    print(f"Loading candidates from {candidates_path}...")
    candidates = load_candidates(candidates_path)
    print(f"Loaded {len(candidates)} candidates")

    print("Computing feature scores...")
    feature_rows = []
    for c in tqdm(candidates, desc="Features"):
        feature_rows.append(get_features(c))

    feat_df = pd.DataFrame(feature_rows)

    combined_skill = (
        feat_df['skill_score'] * 0.5 +
        feat_df['experience_score'] * 0.25 +
        feat_df['title_score'] * 0.15 +
        feat_df['education_score'] * 0.10
    )

    if use_semantic:
        semantic_scores = compute_semantic_scores(candidates)
    else:
        semantic_scores = [0.5] * len(candidates)

    semantic_arr = np.array(semantic_scores)
    behavioral_arr = feat_df['behavioral_score'].values

    final_scores = (
        normalize_0_1(combined_skill.values) * 0.60 +
        normalize_0_1(semantic_arr) * 0.40
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
    parser.add_argument('--no-semantic', action='store_true')
    args = parser.parse_args()

    rank_candidates(args.candidates, args.out, top_n=args.top_n, use_semantic=not args.no_semantic)