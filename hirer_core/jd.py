"""
The job description Hirer ranks against, kept in one place.

Both the command-line ranker (src/ranking.py) and the web backend
(hirer-backend/main.py) import from here, so they always score against
the same text and the same keyword lists.
"""

JD_TITLE = "Senior AI Engineer"

JD_TEXT = """
Senior AI Engineer, founding team role.
Requirements: Production experience with embeddings-based retrieval systems using sentence-transformers,
OpenAI embeddings, BGE, E5 or similar. Vector databases and hybrid search infrastructure:
Pinecone, Weaviate, Qdrant, Milvus, OpenSearch, Elasticsearch, FAISS.
Strong Python. Evaluation frameworks for ranking systems: NDCG, MRR, MAP, A/B testing.
NLP, information retrieval, semantic search, LLM fine-tuning, learning to rank.
5-9 years experience. Location: Pune or Noida India, willing to relocate.
NOT looking for: pure computer vision, speech, robotics without NLP background.
NOT looking for: consulting-only background (TCS, Infosys, Wipro etc).
Looking for: scrappy product engineers who ship, not just researchers.
"""

MUST_HAVE_SKILLS = [
    'embeddings', 'sentence-transformers', 'sentence transformers',
    'vector database', 'vector search', 'faiss', 'pinecone', 'weaviate',
    'qdrant', 'milvus', 'elasticsearch', 'opensearch',
    'python', 'ranking', 'retrieval', 'ndcg', 'mrr', 'information retrieval',
    'nlp', 'llm', 'fine-tuning', 'transformer', 'bert', 'learning to rank',
    'hybrid search', 'bm25', 'semantic search',
]

NICE_TO_HAVE = [
    'lora', 'qlora', 'peft', 'xgboost', 'lightgbm', 'a/b testing',
    'pytorch', 'tensorflow', 'hugging face', 'langchain', 'openai',
    'recommendation system', 'recsys', 'mlops', 'kubernetes', 'docker',
]

# signals that the candidate's focus is outside this role
NEGATIVE_SIGNALS = [
    'computer vision', 'cv', 'image classification', 'object detection',
    'speech recognition', 'robotics', 'ocr',
]

GOOD_TITLES = [
    'ml engineer', 'machine learning engineer', 'ai engineer',
    'nlp engineer', 'search engineer', 'data scientist',
    'senior engineer', 'software engineer', 'backend engineer',
    'research engineer', 'applied scientist',
]
