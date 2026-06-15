import numpy as np


# keywords from the JD
MUST_HAVE_SKILLS = [
    'embeddings', 'sentence-transformers',
    'vector database', 'vector search', 'faiss', 'pinecone',
    'python', 'ranking', 'retrieval', 'nlp', 'llm',
    'ndcg', 'mrr', 'semantic search', 'transformer'
]

NICE_TO_HAVE = [
    'lora', 'qlora', 'pytorch', 'tensorflow',
    'hugging face', 'xgboost', 'a/b testing'
]


def skill_score(candidate):
    all_text = _get_full_text(candidate).lower()

    must_matches = sum(1 for kw in MUST_HAVE_SKILLS if kw in all_text)
    nice_matches = sum(1 for kw in NICE_TO_HAVE if kw in all_text)

    score = (must_matches * 2 + nice_matches * 0.5) / (len(MUST_HAVE_SKILLS) * 2)
    score = min(score, 1.0)
    return score


def _get_full_text(candidate):
    parts = []
    p = candidate.get('profile', {})
    parts.append(p.get('headline', ''))
    parts.append(p.get('summary', ''))
    parts.append(p.get('current_title', ''))

    for job in candidate.get('career_history', []):
        parts.append(job.get('title', ''))
        parts.append(job.get('description', ''))

    for skill in candidate.get('skills', []):
        parts.append(skill.get('name', ''))

    return ' '.join(parts)