"""
extractor.py — Extract structured candidate info from raw resume text
No LLM needed. Uses regex + keyword matching + heuristics.
"""

import re
import uuid
from datetime import datetime
from typing import Optional


# ── Skills database ────────────────────────────────────────────────────────────
KNOWN_SKILLS = [
    # ML / AI
    "python", "machine learning", "deep learning", "nlp", "natural language processing",
    "computer vision", "transformers", "bert", "gpt", "llm", "fine-tuning",
    "sentence-transformers", "embeddings", "vector database", "faiss", "pinecone",
    "weaviate", "qdrant", "milvus", "elasticsearch", "opensearch",
    "semantic search", "hybrid search", "information retrieval", "ranking",
    "ndcg", "mrr", "map", "learning to rank", "bm25", "tfidf",
    "pytorch", "tensorflow", "keras", "scikit-learn", "xgboost", "lightgbm",
    "hugging face", "langchain", "openai", "anthropic", "lora", "qlora", "peft",
    "rag", "retrieval augmented generation", "vector search", "recommendation system",

    # Data
    "pandas", "numpy", "sql", "postgresql", "mysql", "mongodb", "redis",
    "spark", "hadoop", "airflow", "dbt", "data pipeline", "etl",
    "data science", "data analysis", "statistics", "a/b testing",

    # Dev / Infra
    "java", "javascript", "typescript", "react", "next.js", "node.js",
    "fastapi", "flask", "django", "rest api", "graphql",
    "docker", "kubernetes", "aws", "gcp", "azure", "ci/cd",
    "git", "linux", "bash", "mlops", "devops",

    # Research
    "research", "publications", "arxiv", "phd", "thesis",
]

# Institution tier lookup
TIER_1_INSTITUTIONS = [
    "iit", "iim", "iisc", "bits pilani", "nit", "delhi university", "du",
    "mit", "stanford", "harvard", "oxford", "cambridge", "cmu",
    "iit bombay", "iit delhi", "iit madras", "iit kanpur", "iit kharagpur",
    "iit roorkee", "iit guwahati", "iit hyderabad",
]

TIER_2_INSTITUTIONS = [
    "vit", "manipal", "srm", "amity", "symbiosis", "pec", "thapar",
    "dtu", "nsut", "iiit hyderabad", "iiit bangalore", "iiit delhi",
    "jadavpur", "anna university", "pune university", "mumbai university",
]

TIER_3_INSTITUTIONS = [
    "muit", "galgotias", "gl bajaj", "hbtu", "aktu", "mtu",
    "sharda", "bennett", "lovely professional", "lpu",
]


def extract_from_text(text: str, filename: str = "resume") -> dict:
    """
    Main function. Takes raw resume text, returns structured candidate dict
    matching the Hirer candidate schema.
    """
    text_lower = text.lower()
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    candidate_id = f"CAND_{str(uuid.uuid4())[:8].upper()}"

    return {
        "candidate_id": candidate_id,
        "profile": _extract_profile(text, text_lower, lines),
        "skills": _extract_skills(text_lower),
        "career_history": _extract_career(text, lines),
        "education": _extract_education(text, text_lower, lines),
        "certifications": _extract_certifications(text_lower),
        "redrob_signals": _default_signals(),  # can't extract from resume
        "_source_file": filename,
    }


def _extract_profile(text: str, text_lower: str, lines: list) -> dict:
    name = _extract_name(lines)
    email = _extract_email(text)
    phone = _extract_phone(text)
    headline = _extract_headline(lines)
    summary = _extract_summary(text_lower, lines)
    yoe = _extract_yoe(text_lower)
    title = _extract_current_title(lines, text_lower)
    location = _extract_location(text_lower)

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "headline": headline,
        "summary": summary,
        "current_title": title,
        "years_of_experience": yoe,
        "location": location,
        "current_industry": _infer_industry(text_lower),
    }


def _extract_name(lines: list) -> str:
    # Name is usually on the first 1-3 lines, all caps or title case, no special chars
    for line in lines[:4]:
        # skip lines that look like titles/headers
        skip_words = ["resume", "cv", "curriculum", "profile", "portfolio", "contact", "summary"]
        if any(w in line.lower() for w in skip_words):
            continue
        # name pattern: 2-4 words, letters only, title case or all caps
        if re.match(r'^[A-Z][a-zA-Z]+(\s+[A-Z][a-zA-Z]+){1,3}$', line):
            return line.strip()
        if re.match(r'^[A-Z\s]{4,40}$', line) and len(line.split()) <= 4:
            return line.title().strip()
    return "Unknown"


def _extract_email(text: str) -> Optional[str]:
    match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    return match.group(0).lower() if match else None


def _extract_phone(text: str) -> Optional[str]:
    match = re.search(r'(\+?\d[\d\s\-().]{8,15}\d)', text)
    return match.group(0).strip() if match else None


def _extract_headline(lines: list) -> str:
    # headline is usually line 2-5 after the name, short, job-title-like
    title_keywords = ["engineer", "developer", "scientist", "analyst", "manager",
                      "architect", "lead", "researcher", "intern", "consultant",
                      "specialist", "designer", "founder", "director"]
    for line in lines[1:8]:
        if any(kw in line.lower() for kw in title_keywords) and len(line) < 80:
            return line.strip()
    return ""


def _extract_summary(text_lower: str, lines: list) -> str:
    # find summary/objective/about section
    summary_headers = ["summary", "objective", "about me", "profile", "overview", "introduction"]
    for i, line in enumerate(lines):
        if any(h in line.lower() for h in summary_headers) and len(line) < 30:
            # grab next 3-5 lines as summary
            summary_lines = lines[i+1:i+5]
            return " ".join(summary_lines)[:500]
    # fallback: take first paragraph that's long enough
    for line in lines[2:10]:
        if len(line) > 60 and not any(c in line for c in ["@", "http", "github", "linkedin"]):
            return line[:300]
    return ""


def _extract_yoe(text_lower: str) -> float:
    # look for explicit YOE mentions
    patterns = [
        r'(\d+)\+?\s*years?\s+of\s+experience',
        r'(\d+)\+?\s*years?\s+experience',
        r'experience\s+of\s+(\d+)\+?\s*years?',
        r'(\d+)\+?\s*yrs?\s+exp',
    ]
    for pat in patterns:
        m = re.search(pat, text_lower)
        if m:
            return float(m.group(1))

    # calculate from date ranges in career history
    years = _calc_yoe_from_dates(text_lower)
    if years > 0:
        return years

    return 0.0


def _calc_yoe_from_dates(text_lower: str) -> float:
    # find date ranges like "2019 - 2023" or "jan 2020 - present"
    current_year = datetime.now().year
    year_pattern = r'(19|20)\d{2}'
    years_found = [int(y) for y in re.findall(year_pattern, text_lower)]

    if len(years_found) >= 2:
        earliest = min(years_found)
        if 1990 <= earliest <= current_year:
            return float(current_year - earliest)
    return 0.0


def _extract_current_title(lines: list, text_lower: str) -> str:
    title_kws = ["engineer", "developer", "scientist", "analyst", "manager",
                 "architect", "lead", "researcher", "intern", "consultant",
                 "specialist", "director", "founder", "cto", "vp"]

    # look in first 10 lines
    for line in lines[:10]:
        if any(kw in line.lower() for kw in title_kws) and len(line) < 80:
            return line.strip()

    # look for "current role" or "present" near a title
    for i, line in enumerate(lines):
        if "present" in line.lower() or "current" in line.lower():
            for j in range(max(0, i-3), min(len(lines), i+2)):
                if any(kw in lines[j].lower() for kw in title_kws) and len(lines[j]) < 80:
                    return lines[j].strip()
    return "Software Professional"


def _extract_location(text_lower: str) -> str:
    cities = ["bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "pune",
              "chennai", "kolkata", "noida", "gurgaon", "gurugram", "ahmedabad",
              "remote", "work from home", "wfh"]
    for city in cities:
        if city in text_lower:
            return city.title()
    return ""


def _infer_industry(text_lower: str) -> str:
    if any(w in text_lower for w in ["machine learning", "nlp", "ai", "deep learning", "llm"]):
        return "Artificial Intelligence"
    if any(w in text_lower for w in ["software", "developer", "engineer", "backend", "frontend"]):
        return "Software Engineering"
    if any(w in text_lower for w in ["data science", "data analyst", "analytics"]):
        return "Data Science"
    if any(w in text_lower for w in ["devops", "cloud", "infrastructure", "sre"]):
        return "DevOps / Cloud"
    return "Technology"


def _extract_skills(text_lower: str) -> list:
    found = []
    seen = set()
    for skill in KNOWN_SKILLS:
        if skill in text_lower and skill not in seen:
            seen.add(skill)
            # estimate proficiency from context
            proficiency = "intermediate"
            if any(w in text_lower for w in [f"expert in {skill}", f"proficient in {skill}", f"strong {skill}"]):
                proficiency = "expert"
            elif any(w in text_lower for w in [f"learning {skill}", f"basic {skill}", f"beginner"]):
                proficiency = "beginner"

            found.append({
                "name": skill.title(),
                "proficiency": proficiency,
                "duration_months": None,
                "endorsements": 0,
            })
    return found


def _extract_career(text: str, lines: list) -> list:
    career = []
    exp_headers = ["experience", "work experience", "professional experience",
                   "employment", "work history", "career"]

    # find experience section
    exp_start = -1
    for i, line in enumerate(lines):
        if any(h == line.lower().strip() for h in exp_headers):
            exp_start = i
            break

    if exp_start == -1:
        return _fallback_career(lines)

    # parse jobs from experience section
    job_lines = lines[exp_start+1:]
    current_job = None
    desc_lines = []

    for line in job_lines[:60]:  # limit to 60 lines
        # stop at next major section
        if any(h in line.lower() for h in ["education", "skills", "certification", "project", "achievement"]) and len(line) < 30:
            break

        # detect company/title line (title case, short)
        year_match = re.search(r'(19|20)\d{2}', line)
        if year_match and len(line) < 100:
            if current_job and desc_lines:
                current_job["description"] = " ".join(desc_lines[:5])
                career.append(current_job)
            # parse years
            years = re.findall(r'(19|20)\d{2}', line)
            start_year = int(years[0]) if years else None
            end_year = int(years[1]) if len(years) > 1 else datetime.now().year
            current_job = {
                "title": "",
                "company": "",
                "start_year": start_year,
                "end_year": end_year,
                "description": "",
                "is_current": "present" in line.lower() or end_year == datetime.now().year,
            }
            desc_lines = []
        elif current_job is not None:
            if not current_job["title"] and len(line) < 80:
                current_job["title"] = line.strip()
            elif not current_job["company"] and len(line) < 60:
                current_job["company"] = line.strip()
            else:
                desc_lines.append(line.strip())

    if current_job and desc_lines:
        current_job["description"] = " ".join(desc_lines[:5])
        career.append(current_job)

    return career[:6]  # max 6 jobs


def _fallback_career(lines: list) -> list:
    """fallback: just find any lines that look like job titles"""
    title_kws = ["engineer", "developer", "analyst", "manager", "scientist", "intern", "lead"]
    jobs = []
    for line in lines:
        if any(kw in line.lower() for kw in title_kws) and len(line) < 80 and len(line) > 5:
            jobs.append({"title": line.strip(), "company": "", "description": "", "start_year": None, "end_year": None, "is_current": False})
            if len(jobs) >= 3:
                break
    return jobs


def _extract_education(text: str, text_lower: str, lines: list) -> list:
    edu = []
    degree_patterns = [
        (r'\bb\.?tech\b', "B.Tech"), (r'\bb\.?e\b', "B.E."),
        (r'\bm\.?tech\b', "M.Tech"), (r'\bm\.?e\b', "M.E."),
        (r'\bb\.?sc\b', "B.Sc"), (r'\bm\.?sc\b', "M.Sc"),
        (r'\bmba\b', "MBA"), (r'\bphd\b', "PhD"),
        (r'\bb\.?c\.?a\b', "BCA"), (r'\bm\.?c\.?a\b', "MCA"),
        (r'\bbachelor', "Bachelor's"), (r'\bmaster', "Master's"),
    ]

    for pat, degree_name in degree_patterns:
        m = re.search(pat, text_lower)
        if m:
            # find institution near this match
            start = max(0, m.start() - 200)
            end = min(len(text_lower), m.end() + 200)
            context = text_lower[start:end]

            institution = _find_institution(context)
            tier = _get_tier(context)
            years = re.findall(r'(19|20)\d{2}', text[start:end])

            edu.append({
                "degree": degree_name,
                "field_of_study": _extract_field(context),
                "institution": institution,
                "tier": tier,
                "start_year": int(years[0]) if len(years) >= 1 else None,
                "end_year": int(years[1]) if len(years) >= 2 else None,
                "grade": _extract_grade(context),
            })
            if len(edu) >= 3:
                break

    return edu


def _find_institution(context: str) -> str:
    # look for known institution names
    for inst in TIER_1_INSTITUTIONS + TIER_2_INSTITUTIONS + TIER_3_INSTITUTIONS:
        if inst in context:
            return inst.upper() if len(inst) <= 4 else inst.title()
    # look for "university" or "college" nearby
    m = re.search(r'([a-z\s]+(?:university|college|institute|school)[a-z\s]*)', context)
    if m:
        return m.group(0).strip().title()[:50]
    return "Unknown Institution"


def _get_tier(context: str) -> str:
    for inst in TIER_1_INSTITUTIONS:
        if inst in context:
            return "tier_1"
    for inst in TIER_2_INSTITUTIONS:
        if inst in context:
            return "tier_2"
    for inst in TIER_3_INSTITUTIONS:
        if inst in context:
            return "tier_3"
    return "unknown"


def _extract_field(context: str) -> str:
    fields = {
        "computer science": ["computer science", "cse", "cs"],
        "data science": ["data science", "data analytics"],
        "electronics": ["electronics", "ece", "electrical"],
        "mechanical": ["mechanical", "me"],
        "information technology": ["information technology", "it"],
        "ai/ml": ["artificial intelligence", "machine learning", "ai"],
    }
    for field_name, kws in fields.items():
        if any(kw in context for kw in kws):
            return field_name.title()
    return "Engineering"


def _extract_grade(context: str) -> Optional[str]:
    # CGPA
    m = re.search(r'(\d+\.?\d*)\s*(?:cgpa|gpa|cpi)', context)
    if m:
        return f"{m.group(1)} CGPA"
    # percentage
    m = re.search(r'(\d+\.?\d*)\s*%', context)
    if m:
        return f"{m.group(1)}%"
    return None


def _extract_certifications(text_lower: str) -> list:
    certs = []
    cert_keywords = [
        "aws certified", "google cloud", "azure certified", "gcp",
        "tensorflow certificate", "pytorch", "coursera", "udemy",
        "deep learning specialization", "machine learning",
        "data science", "nlp specialization",
    ]
    for kw in cert_keywords:
        if kw in text_lower:
            certs.append({"name": kw.title(), "issuer": "Online", "year": None})
    return certs[:5]


def _default_signals() -> dict:
    """
    Behavioral signals can't be extracted from a resume.
    Use neutral defaults that don't penalize the candidate.
    """
    return {
        "open_to_work_flag": True,  # they submitted a resume, so yes
        "recruiter_response_rate": 0.75,
        "avg_response_time_hours": 24,
        "last_active_date": datetime.now().strftime("%Y-%m-%d"),
        "github_activity_score": -1,  # unknown
        "profile_completeness_score": 70,
        "notice_period_days": 30,
    }
