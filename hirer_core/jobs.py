"""
Jobs that candidates are ranked against.

A Job can come from three places: the built-in presets, a job description
someone pastes in (parse_job reads the skills, experience range and
locations out of it), or the default Senior AI Engineer role.
"""

import re
from dataclasses import dataclass, field, asdict

from .skills import find_skills

CITIES = ['bangalore', 'bengaluru', 'mumbai', 'delhi', 'hyderabad', 'pune', 'chennai', 'kolkata',
          'noida', 'gurgaon', 'gurugram', 'ahmedabad', 'jaipur', 'indore', 'kochi', 'chandigarh',
          'coimbatore', 'bhubaneswar', 'lucknow', 'new york', 'san francisco', 'london',
          'singapore', 'dubai', 'berlin', 'toronto', 'remote']


@dataclass
class Job:
    title: str
    text: str = ''
    must_have: list = field(default_factory=list)
    nice_to_have: list = field(default_factory=list)
    negative: list = field(default_factory=list)
    good_titles: list = field(default_factory=list)
    years: tuple | None = None        # (low, high); high None means "low or more"
    locations: list = field(default_factory=list)
    id: int | None = None
    domain: str = ''
    company: str = ''

    def __post_init__(self):
        if not self.text:
            self.text = self.query()

    def query(self):
        """short version of the job, used where the full text is too long"""
        parts = [self.title + '.']
        if self.must_have:
            parts.append('Required skills: ' + ', '.join(self.must_have) + '.')
        if self.nice_to_have:
            parts.append('Nice to have: ' + ', '.join(self.nice_to_have) + '.')
        if self.years:
            lo, hi = self.years
            parts.append(f'{lo}-{hi} years experience.' if hi else f'{lo}+ years experience.')
        if self.locations:
            parts.append('Location: ' + ', '.join(self.locations) + '.')
        return ' '.join(parts)

    def to_dict(self):
        d = asdict(self)
        d.pop('text')
        return d


DEFAULT_JOB = Job(
    id=1, domain='AI/ML', company='Redrob AI', title='Senior AI Engineer',
    text="""
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
""",
    must_have=['embedding', 'sentence-transformers', 'vector database', 'vector search', 'faiss',
               'pinecone', 'weaviate', 'qdrant', 'milvus', 'elasticsearch', 'opensearch', 'python',
               'ranking', 'retrieval', 'ndcg', 'mrr', 'information retrieval', 'nlp', 'llm',
               'fine-tuning', 'transformer', 'bert', 'learning to rank', 'hybrid search', 'bm25',
               'semantic search'],
    nice_to_have=['lora', 'qlora', 'peft', 'xgboost', 'lightgbm', 'a/b testing', 'pytorch',
                  'tensorflow', 'hugging face', 'langchain', 'openai', 'recommendation system',
                  'mlops', 'kubernetes', 'docker'],
    negative=['computer vision', 'image classification', 'object detection', 'speech recognition',
              'robotics', 'ocr'],
    good_titles=['ml engineer', 'machine learning engineer', 'ai engineer', 'nlp engineer',
                 'search engineer', 'data scientist', 'senior engineer', 'software engineer',
                 'backend engineer', 'research engineer', 'applied scientist'],
    years=(5, 9),
    locations=['pune', 'noida'],
)

# (id, domain, title, company, keywords, years)
_PRESETS = [
    (2,  'AI/ML',     'ML Platform Engineer',      'FinTech Corp',  ['mlops', 'kubernetes', 'pytorch', 'spark', 'docker', 'data pipeline', 'infrastructure', 'airflow'], (3, 8)),
    (3,  'AI/ML',     'NLP Researcher',            'AI Labs India', ['nlp', 'bert', 'transformer', 'research', 'publications', 'language model'], (2, 8)),
    (4,  'Data',      'Data Scientist',            'Flipkart',      ['xgboost', 'sql', 'analytics', 'python', 'statistics', 'a/b testing', 'pandas', 'visualization'], (2, 7)),
    (5,  'Backend',   'Backend Engineer',          'Startup',       ['python', 'fastapi', 'postgresql', 'redis', 'rest api', 'docker', 'microservices'], (2, 7)),
    (6,  'Frontend',  'Frontend Developer',        'SaaS Co',       ['react', 'javascript', 'typescript', 'css', 'html', 'next.js', 'ui', 'tailwind', 'figma'], (1, 6)),
    (7,  'Mobile',    'Android Developer',         'App Studio',    ['android', 'kotlin', 'java', 'jetpack', 'firebase', 'mobile', 'gradle', 'xml'], (1, 6)),
    (8,  'Mobile',    'iOS Developer',             'Product Co',    ['ios', 'swift', 'xcode', 'swiftui', 'objective-c', 'apple', 'mobile'], (1, 6)),
    (9,  'Mobile',    'Flutter Developer',         'Agency',        ['flutter', 'dart', 'android', 'ios', 'firebase', 'mobile', 'cross-platform'], (1, 5)),
    (10, 'DevOps',    'DevOps Engineer',           'Cloud Corp',    ['docker', 'kubernetes', 'aws', 'gcp', 'azure', 'ci/cd', 'terraform', 'jenkins', 'linux', 'bash'], (2, 8)),
    (11, 'DevOps',    'Cloud Architect',           'Enterprise Co', ['aws', 'gcp', 'azure', 'cloud', 'architecture', 'microservices', 'terraform', 'security'], (6, 15)),
    (12, 'DevOps',    'Site Reliability Engineer', 'Tech Giant',    ['sre', 'kubernetes', 'monitoring', 'prometheus', 'grafana', 'linux', 'on-call', 'reliability'], (3, 10)),
    (13, 'Fullstack', 'Full Stack Developer',      'Startup',       ['react', 'node.js', 'python', 'postgresql', 'rest api', 'docker', 'javascript', 'typescript'], (2, 7)),
    (14, 'Data',      'Data Engineer',             'Analytics Co',  ['spark', 'airflow', 'dbt', 'sql', 'python', 'etl', 'data pipeline', 'kafka', 'data warehouse'], (2, 8)),
    (15, 'Data',      'Business Analyst',          'Consulting',    ['sql', 'excel', 'tableau', 'power bi', 'analytics', 'requirements', 'stakeholder', 'dashboard'], (1, 6)),
    (16, 'Security',  'Cybersecurity Analyst',     'SecureNet',     ['security', 'penetration testing', 'vulnerability', 'firewall', 'siem', 'compliance', 'linux', 'python'], (1, 7)),
    (17, 'Product',   'Product Manager',           'Product Co',    ['product management', 'roadmap', 'agile', 'scrum', 'user research', 'metrics', 'stakeholder', 'jira'], (3, 10)),
    (18, 'Design',    'UI/UX Designer',            'Design Studio', ['figma', 'ui', 'ux', 'user research', 'wireframe', 'prototype', 'design system', 'adobe'], (1, 7)),
    (19, 'Finance',   'Financial Analyst',         'Finance Corp',  ['finance', 'excel', 'financial modeling', 'accounting', 'sql', 'valuation', 'reporting', 'cfa'], (1, 7)),
    (20, 'Marketing', 'Digital Marketing Manager', 'Brand Co',      ['marketing', 'seo', 'content', 'social media', 'analytics', 'campaign', 'brand', 'google ads'], (3, 10)),
]

PRESETS = [DEFAULT_JOB] + [
    Job(id=i, domain=d, title=t, company=c, must_have=kw, years=y, good_titles=[t.lower()])
    for i, d, t, c, kw, y in _PRESETS
]
_BY_ID = {j.id: j for j in PRESETS}


# ── reading a pasted job description ─────────────────────────────────────────

_NICE = re.compile(r'nice[- ]to[- ]have|good[- ]to[- ]have|preferred|bonus|is a plus|are a plus|a plus\b|desirable|optional', re.I)
_MUST = re.compile(r'requirements?|required|must[- ]have|qualifications|what you.ll (do|need)|responsibilities|you have|essential', re.I)
_NOT = re.compile(r"not looking for|not a fit|do not apply|don.t apply|we are not|no experience (in|with) .* (is )?needed", re.I)
_RANGE = re.compile(r'(\d{1,2})\s*(?:-|–|—|to)\s*(\d{1,2})\+?\s*(?:years|yrs)', re.I)
_MIN = re.compile(r'(?:(?:at least|minimum(?: of)?|min\.?)\s*(\d{1,2})\s*(?:years|yrs))|(?:(\d{1,2})\s*\+\s*(?:years|yrs))', re.I)


def _is_header(line, pattern):
    """a section heading such as 'Nice to have:' rather than a sentence that happens to say 'preferred'"""
    m = pattern.search(line)
    return bool(m) and (m.start() < 4 and (len(line) < 40 or ':' in line[:m.end() + 3]))


def parse_job(text, extra_skills=None):
    """Build a Job from a pasted job description."""
    lines = [l.strip(' \t•*-–·') for l in text.splitlines()]
    lines = [l for l in lines if l]
    title = 'Custom job'
    if lines and len(lines[0]) <= 80 and not lines[0].endswith('.'):
        title = re.sub(r'^(job title|role|position|title)\s*[:\-]\s*', '', lines[0], flags=re.I).strip() or title

    must, nice, negative = [], [], []
    mode = must
    for line in lines:
        if _NOT.search(line):
            negative += find_skills(line)
            continue
        if _is_header(line, _NICE):
            mode = nice
        elif _is_header(line, _MUST):
            mode = must
        # "Kubernetes is a plus" inside the requirements still means nice-to-have
        target = nice if (mode is must and _NICE.search(line)) else mode
        target += find_skills(line)

    for s in (extra_skills or []):
        s = s.strip().lower()
        if s:
            must.append(s)

    def unique(items, exclude=()):
        out = []
        for i in items:
            if i not in out and i not in exclude:
                out.append(i)
        return out

    negative = unique(negative)
    must = unique(must, negative)
    nice = unique(nice, set(must) | set(negative))
    if not must and nice:
        must, nice = nice, []

    years = None
    m = _RANGE.search(text)
    if m and int(m.group(1)) <= int(m.group(2)):
        years = (int(m.group(1)), int(m.group(2)))
    else:
        m = _MIN.search(text)
        if m:
            years = (int(m.group(1) or m.group(2)), None)

    low = text.lower()
    locations = [c for c in CITIES if re.search(r'(?<![a-z])' + re.escape(c) + r'(?![a-z])', low)]

    return Job(title=title, text=text.strip(), must_have=must, nice_to_have=nice, negative=negative,
               years=years, locations=locations)


def get_job(preset=None, text=None, extra_skills=None):
    """the job to rank against: pasted text wins, then a preset id, then the default"""
    if text and text.strip():
        return parse_job(text, extra_skills)
    if preset is not None:
        if preset not in _BY_ID:
            raise ValueError(f'Unknown job preset: {preset}')
        return _BY_ID[preset]
    return DEFAULT_JOB

