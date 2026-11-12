"""
Skill vocabulary: one canonical name per skill, plus the other ways people
write it. Used to read skills out of job descriptions and resumes, and to
match the two so that "k8s" on a resume counts for "kubernetes" in a job.
"""

from .utils import contains_term

VOCAB = {
    # search and retrieval
    'embedding': ['vector embedding', 'text embedding'],
    'sentence-transformers': ['sentence transformers', 'sbert'],
    'vector database': ['vector db', 'vector store'],
    'vector search': ['similarity search', 'nearest neighbor search', 'nearest neighbour search'],
    'faiss': [], 'pinecone': [], 'weaviate': [], 'qdrant': [], 'milvus': [],
    'chroma': ['chromadb'], 'pgvector': [],
    'elasticsearch': ['elastic search'], 'opensearch': [],
    'semantic search': [], 'hybrid search': [], 'bm25': [], 'tf-idf': ['tfidf'],
    'information retrieval': [], 'retrieval': [],
    'ranking': ['ranker', 'reranking', 're-ranking', 'reranker'],
    'learning to rank': ['learning-to-rank', 'ltr', 'lambdamart'],
    'ndcg': [], 'mrr': [],
    'rag': ['retrieval augmented generation', 'retrieval-augmented generation'],
    'recommendation system': ['recommender system', 'recsys', 'recommendation engine'],
    # machine learning
    'python': [], 'machine learning': ['ml'], 'deep learning': [],
    'nlp': ['natural language processing'],
    'llm': ['large language model'], 'gpt': [], 'bert': [],
    'transformer': [], 'language model': [],
    'fine-tuning': ['fine tuning', 'finetuning', 'fine-tune', 'fine-tuned', 'finetuned'],
    'lora': [], 'qlora': [], 'peft': [],
    'pytorch': ['torch'], 'tensorflow': [], 'keras': [], 'scikit-learn': ['sklearn', 'scikit learn'],
    'xgboost': [], 'lightgbm': [], 'hugging face': ['huggingface'], 'langchain': [], 'openai': [],
    'mlops': [], 'mlflow': [], 'statistics': ['statistical modeling'], 'a/b testing': ['ab testing', 'a/b test'],
    'computer vision': [], 'opencv': [], 'image classification': [], 'object detection': ['yolo'],
    'speech recognition': ['asr'], 'ocr': [], 'robotics': [],
    # data
    'sql': [], 'postgresql': ['postgres'], 'mysql': [], 'mongodb': ['mongo'], 'redis': [],
    'spark': ['pyspark'], 'hadoop': [], 'kafka': [], 'airflow': [], 'dbt': [],
    'etl': ['elt'], 'data pipeline': [], 'data warehouse': ['snowflake', 'bigquery', 'redshift'],
    'pandas': [], 'numpy': [], 'analytics': ['data analysis', 'data analytics'], 'data science': [],
    'visualization': ['data visualization', 'matplotlib'], 'tableau': [], 'power bi': ['powerbi'],
    'excel': [], 'r programming': [],
    # backend and infrastructure
    'java': [], 'golang': [], 'c++': [], 'rust': [],
    'fastapi': [], 'flask': [], 'django': [], 'rest api': ['restful api', 'rest apis'], 'graphql': [],
    'microservices': ['microservice'], 'docker': [], 'kubernetes': ['k8s'],
    'aws': ['amazon web services'], 'gcp': ['google cloud'], 'azure': [],
    'ci/cd': ['cicd', 'ci cd', 'continuous integration'], 'terraform': [], 'jenkins': [],
    'linux': [], 'bash': ['shell scripting'], 'git': [], 'devops': [], 'sre': ['site reliability'],
    'observability': [], 'prometheus': [], 'grafana': [], 'system design': [],
    'cybersecurity': ['infosec', 'information security'],
    'penetration testing': ['pentesting', 'pen testing'], 'firewall': [], 'siem': [],
    # frontend and mobile
    'javascript': ['js'], 'typescript': [], 'react': ['reactjs', 'react.js'], 'next.js': ['nextjs'],
    'node.js': ['nodejs'], 'vue': ['vue.js'], 'angular': [], 'html': [], 'css': [],
    'tailwind': ['tailwindcss'], 'ui': ['user interface'], 'ux': ['user experience'], 'figma': [],
    'wireframe': ['wireframing'], 'prototype': ['prototyping'], 'design system': [], 'adobe': [],
    'android': [], 'kotlin': [], 'jetpack': [], 'gradle': [], 'xml': [], 'firebase': [],
    'ios': [], 'swift': [], 'swiftui': [], 'xcode': [], 'objective-c': [],
    'flutter': [], 'dart': [], 'react native': [],
    # product, business
    'product management': [], 'agile': [], 'scrum': [], 'jira': [],
    'user research': [], 'stakeholder management': [],
    'finance': [], 'financial modeling': ['financial modelling'], 'accounting': [], 'valuation': [], 'cfa': [],
    'marketing': ['digital marketing'], 'seo': [], 'content writing': ['content marketing'],
    'social media': [], 'google ads': ['adwords'],
    'blockchain': ['web3', 'solidity'],
}

ALIASES = {name: (name, *others) for name, others in VOCAB.items()}

_UPPER = {'nlp', 'llm', 'gpt', 'bert', 'rag', 'sql', 'aws', 'gcp', 'etl', 'dbt', 'ocr', 'seo', 'cfa', 'sre',
          'ui', 'ux', 'xml', 'css', 'html', 'ndcg', 'mrr', 'bm25', 'faiss', 'lora', 'qlora', 'peft',
          'siem', 'ci/cd'}
_DISPLAY = {'mlops': 'MLOps', 'devops': 'DevOps', 'ios': 'iOS', 'pytorch': 'PyTorch', 'tensorflow': 'TensorFlow',
            'postgresql': 'PostgreSQL', 'mysql': 'MySQL', 'mongodb': 'MongoDB', 'javascript': 'JavaScript',
            'typescript': 'TypeScript', 'fastapi': 'FastAPI', 'graphql': 'GraphQL', 'xgboost': 'XGBoost',
            'lightgbm': 'LightGBM', 'langchain': 'LangChain', 'openai': 'OpenAI', 'opencv': 'OpenCV',
            'mlflow': 'MLflow', 'swiftui': 'SwiftUI', 'a/b testing': 'A/B Testing', 'tf-idf': 'TF-IDF'}


def term_in(text, term):
    """True if the skill, or any other way of writing it, appears as a whole word. text must be lowercase."""
    return any(contains_term(text, a) for a in ALIASES.get(term, (term,)))


def find_skills(text):
    """every vocabulary skill mentioned in the text, in vocabulary order"""
    text = text.lower()
    return [name for name in VOCAB if term_in(text, name)]


def display(name):
    """how a canonical skill name is shown to people"""
    if name in _DISPLAY:
        return _DISPLAY[name]
    if name in _UPPER:
        return name.upper()
    if any(ch in name for ch in './+'):
        return name[0].upper() + name[1:]
    return name.title()
