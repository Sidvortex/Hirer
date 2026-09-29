"""
extractor.py — Extract structured candidate info from raw resume text
No LLM. Uses regex + keyword matching + heuristics.
Also handles OCR for scanned/image PDFs via pytesseract.
"""

import re
import uuid
from datetime import datetime
from typing import Optional


KNOWN_SKILLS = [
    # ML / AI
    "python", "machine learning", "deep learning", "nlp", "natural language processing",
    "computer vision", "transformers", "bert", "gpt", "llm", "fine-tuning",
    "sentence-transformers", "embeddings", "vector database", "faiss", "pinecone",
    "weaviate", "qdrant", "milvus", "elasticsearch", "opensearch",
    "semantic search", "hybrid search", "information retrieval", "ranking",
    "ndcg", "mrr", "map", "learning to rank", "bm25", "tfidf",
    "pytorch", "tensorflow", "keras", "scikit-learn", "xgboost", "lightgbm",
    "hugging face", "langchain", "openai", "lora", "qlora", "peft",
    "rag", "retrieval augmented generation", "recommendation system",
    # Data
    "pandas", "numpy", "sql", "postgresql", "mysql", "mongodb", "redis",
    "spark", "hadoop", "airflow", "dbt", "data pipeline", "etl",
    "data science", "data analysis", "statistics", "a/b testing",
    "tableau", "power bi", "excel", "r programming",
    # Dev / Infra
    "java", "javascript", "typescript", "react", "next.js", "node.js",
    "vue", "angular", "fastapi", "flask", "django", "rest api", "graphql",
    "docker", "kubernetes", "aws", "gcp", "azure", "ci/cd", "terraform",
    "git", "linux", "bash", "mlops", "devops",
    # Other domains
    "android", "ios", "swift", "kotlin", "flutter", "react native",
    "figma", "ui/ux", "product management", "agile", "scrum",
    "cybersecurity", "blockchain", "web3", "solidity",
    "finance", "accounting", "financial modeling",
    "digital marketing", "seo", "content writing",
    "research", "publications",
]

TIER_1 = ["iit", "iim", "iisc", "bits pilani", "nit", "mit", "stanford", "harvard", "oxford", "cambridge", "cmu",
           "iit bombay", "iit delhi", "iit madras", "iit kanpur", "iit kharagpur", "iit roorkee", "iit guwahati"]
TIER_2 = ["vit", "manipal", "srm", "amity", "symbiosis", "pec", "thapar", "dtu", "nsut",
           "iiit hyderabad", "iiit bangalore", "iiit delhi", "jadavpur", "anna university"]
TIER_3 = ["muit", "galgotias", "gl bajaj", "hbtu", "aktu", "mtu", "sharda", "bennett",
           "lovely professional", "lpu", "maharishi"]


def extract_text_from_pdf(pdf_path: str) -> str:
    """Try pdfplumber first, fall back to OCR if empty."""
    text = ""

    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        pass

    if text.strip():
        return text

    # Fallback to OCR for scanned/image PDFs
    try:
        import pytesseract
        from pdf2image import convert_from_path
        pages = convert_from_path(pdf_path, dpi=200)
        ocr_parts = []
        for page in pages:
            ocr_parts.append(pytesseract.image_to_string(page))
        text = "\n".join(ocr_parts)
    except Exception:
        pass

    return text


def extract_text_from_image(image_path: str) -> str:
    """OCR on a direct image upload (JPG/PNG)."""
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(image_path)
        return pytesseract.image_to_string(img)
    except Exception as e:
        raise ValueError(f"Could not read image: {e}")


def extract_from_text(text: str, filename: str = "resume") -> dict:
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
        "redrob_signals": _default_signals(),
        "_source_file": filename,
    }


def _extract_profile(text, text_lower, lines):
    return {
        "name": _extract_name(lines),
        "email": _extract_email(text),
        "phone": _extract_phone(text),
        "headline": _extract_headline(lines),
        "summary": _extract_summary(text_lower, lines),
        "current_title": _extract_current_title(lines, text_lower),
        "years_of_experience": _extract_yoe(text_lower),
        "location": _extract_location(text_lower),
        "current_industry": _infer_industry(text_lower),
    }


def _extract_name(lines):
    for line in lines[:4]:
        skip = ["resume", "cv", "curriculum", "profile", "portfolio", "contact", "summary"]
        if any(w in line.lower() for w in skip):
            continue
        if re.match(r'^[A-Z][a-zA-Z]+(\s+[A-Z][a-zA-Z]+){1,3}$', line):
            return line.strip()
        if re.match(r'^[A-Z\s]{4,40}$', line) and len(line.split()) <= 4:
            return line.title().strip()
    return "Unknown"


def _extract_email(text):
    m = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    return m.group(0).lower() if m else None


def _extract_phone(text):
    m = re.search(r'(\+?\d[\d\s\-().]{8,15}\d)', text)
    return m.group(0).strip() if m else None


def _extract_headline(lines):
    kws = ["engineer", "developer", "scientist", "analyst", "manager", "architect",
           "lead", "researcher", "intern", "consultant", "specialist", "designer",
           "founder", "director", "cto", "vp", "product", "marketing", "finance"]
    for line in lines[1:8]:
        if any(kw in line.lower() for kw in kws) and len(line) < 80:
            return line.strip()
    return ""


def _extract_summary(text_lower, lines):
    headers = ["summary", "objective", "about me", "profile", "overview", "introduction", "about"]
    for i, line in enumerate(lines):
        if any(h == line.lower().strip() for h in headers):
            return " ".join(lines[i+1:i+5])[:500]
    for line in lines[2:10]:
        if len(line) > 60 and not any(c in line for c in ["@", "http", "github", "linkedin"]):
            return line[:300]
    return ""


def _extract_yoe(text_lower):
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
    return _calc_yoe_from_dates(text_lower)


def _calc_yoe_from_dates(text_lower):
    current_year = datetime.now().year
    years_found = [int(y) for y in re.findall(r'(19|20)\d{2}', text_lower)]
    if len(years_found) >= 2:
        earliest = min(years_found)
        if 1990 <= earliest <= current_year:
            return float(current_year - earliest)
    return 0.0


def _extract_current_title(lines, text_lower):
    kws = ["engineer", "developer", "scientist", "analyst", "manager", "architect",
           "lead", "researcher", "intern", "consultant", "specialist", "director",
           "founder", "cto", "vp", "designer", "product", "marketing", "accountant"]
    for line in lines[:10]:
        if any(kw in line.lower() for kw in kws) and len(line) < 80:
            return line.strip()
    for i, line in enumerate(lines):
        if "present" in line.lower() or "current" in line.lower():
            for j in range(max(0, i-3), min(len(lines), i+2)):
                if any(kw in lines[j].lower() for kw in kws) and len(lines[j]) < 80:
                    return lines[j].strip()
    return "Professional"


def _extract_location(text_lower):
    cities = ["bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "pune",
              "chennai", "kolkata", "noida", "gurgaon", "gurugram", "ahmedabad",
              "remote", "new york", "san francisco", "london", "singapore"]
    for city in cities:
        if city in text_lower:
            return city.title()
    return ""


def _infer_industry(text_lower):
    if any(w in text_lower for w in ["machine learning", "nlp", "ai", "deep learning", "llm"]):
        return "Artificial Intelligence"
    if any(w in text_lower for w in ["frontend", "react", "vue", "angular", "ui/ux"]):
        return "Frontend Development"
    if any(w in text_lower for w in ["backend", "fastapi", "django", "flask", "node"]):
        return "Backend Development"
    if any(w in text_lower for w in ["devops", "kubernetes", "docker", "cloud", "aws", "gcp"]):
        return "DevOps / Cloud"
    if any(w in text_lower for w in ["data science", "analytics", "tableau", "power bi"]):
        return "Data Science"
    if any(w in text_lower for w in ["android", "ios", "flutter", "react native"]):
        return "Mobile Development"
    if any(w in text_lower for w in ["finance", "accounting", "financial"]):
        return "Finance"
    if any(w in text_lower for w in ["marketing", "seo", "content", "brand"]):
        return "Marketing"
    if any(w in text_lower for w in ["software", "developer", "engineer"]):
        return "Software Engineering"
    return "Technology"


def _extract_skills(text_lower):
    found = []
    seen = set()
    for skill in KNOWN_SKILLS:
        if skill in text_lower and skill not in seen:
            seen.add(skill)
            proficiency = "intermediate"
            if any(w in text_lower for w in [f"expert in {skill}", f"proficient in {skill}", f"strong {skill}"]):
                proficiency = "expert"
            elif any(w in text_lower for w in [f"learning {skill}", f"basic {skill}"]):
                proficiency = "beginner"
            found.append({"name": skill.title(), "proficiency": proficiency, "duration_months": None, "endorsements": 0})
    return found


def _extract_career(text, lines):
    career = []
    exp_headers = ["experience", "work experience", "professional experience", "employment", "work history", "career"]
    exp_start = -1
    for i, line in enumerate(lines):
        if any(h == line.lower().strip() for h in exp_headers):
            exp_start = i
            break
    if exp_start == -1:
        return _fallback_career(lines)

    job_lines = lines[exp_start+1:]
    current_job = None
    desc_lines = []
    for line in job_lines[:60]:
        if any(h in line.lower() for h in ["education", "skills", "certification", "project", "achievement"]) and len(line) < 30:
            break
        year_match = re.search(r'(19|20)\d{2}', line)
        if year_match and len(line) < 100:
            if current_job and desc_lines:
                current_job["description"] = " ".join(desc_lines[:5])
                career.append(current_job)
            years = re.findall(r'(19|20)\d{2}', line)
            current_job = {
                "title": "", "company": "",
                "start_year": int(years[0]) if years else None,
                "end_year": int(years[1]) if len(years) > 1 else datetime.now().year,
                "description": "",
                "is_current": "present" in line.lower(),
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
    return career[:6]


def _fallback_career(lines):
    kws = ["engineer", "developer", "analyst", "manager", "scientist", "intern", "lead", "designer"]
    jobs = []
    for line in lines:
        if any(kw in line.lower() for kw in kws) and 5 < len(line) < 80:
            jobs.append({"title": line.strip(), "company": "", "description": "", "start_year": None, "end_year": None, "is_current": False})
            if len(jobs) >= 3:
                break
    return jobs


def _extract_education(text, text_lower, lines):
    edu = []
    degree_patterns = [
        (r'\bb\.?tech\b', "B.Tech"), (r'\bb\.?e\b', "B.E."),
        (r'\bm\.?tech\b', "M.Tech"), (r'\bmba\b', "MBA"),
        (r'\bphd\b', "PhD"), (r'\bb\.?sc\b', "B.Sc"),
        (r'\bm\.?sc\b', "M.Sc"), (r'\bbachelor', "Bachelor's"),
        (r'\bmaster', "Master's"), (r'\bb\.?c\.?a\b', "BCA"),
        (r'\bm\.?c\.?a\b', "MCA"),
    ]
    for pat, degree_name in degree_patterns:
        m = re.search(pat, text_lower)
        if m:
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


def _find_institution(context):
    for inst in TIER_1 + TIER_2 + TIER_3:
        if inst in context:
            return inst.upper() if len(inst) <= 4 else inst.title()
    m = re.search(r'([a-z\s]+(?:university|college|institute|school)[a-z\s]*)', context)
    if m:
        return m.group(0).strip().title()[:50]
    return "Unknown Institution"


def _get_tier(context):
    for inst in TIER_1:
        if inst in context: return "tier_1"
    for inst in TIER_2:
        if inst in context: return "tier_2"
    for inst in TIER_3:
        if inst in context: return "tier_3"
    return "unknown"


def _extract_field(context):
    fields = {
        "Computer Science": ["computer science", "cse", "cs"],
        "Data Science": ["data science", "data analytics"],
        "Electronics": ["electronics", "ece", "electrical"],
        "Mechanical": ["mechanical", "me"],
        "Information Technology": ["information technology", "it"],
        "AI/ML": ["artificial intelligence", "machine learning"],
        "Civil": ["civil engineering", "civil"],
        "Finance": ["finance", "commerce", "accounting"],
        "Design": ["design", "ux", "ui"],
    }
    for field_name, kws in fields.items():
        if any(kw in context for kw in kws):
            return field_name
    return "Engineering"


def _extract_grade(context):
    m = re.search(r'(\d+\.?\d*)\s*(?:cgpa|gpa|cpi)', context)
    if m: return f"{m.group(1)} CGPA"
    m = re.search(r'(\d+\.?\d*)\s*%', context)
    if m: return f"{m.group(1)}%"
    return None


def _extract_certifications(text_lower):
    certs = []
    cert_kws = ["aws certified", "google cloud", "azure certified", "gcp certified",
                "tensorflow certificate", "coursera", "udemy", "deep learning specialization",
                "machine learning", "data science", "nlp specialization", "pmp", "cfa"]
    for kw in cert_kws:
        if kw in text_lower:
            certs.append({"name": kw.title(), "issuer": "Online", "year": None})
    return certs[:5]


def _default_signals():
    return {
        "open_to_work_flag": True,
        "recruiter_response_rate": 0.75,
        "avg_response_time_hours": 24,
        "last_active_date": datetime.now().strftime("%Y-%m-%d"),
        "github_activity_score": -1,
        "profile_completeness_score": 70,
        "notice_period_days": 30,
    }
