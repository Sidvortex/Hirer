"""
Helpers for the resume modes: applying a person's edits to an extracted
resume, reading detail files that sit next to resumes in a ZIP, and matching
a single resume against the job list.
"""

import csv
import io
import json
import re
from pathlib import PurePosixPath

from hirer_core.features import experience_score, has_details
from hirer_core.utils import contains_term

RESUME_EXTS = (".pdf", ".jpg", ".jpeg", ".png", ".webp")

# ── editable fields ──────────────────────────────────────────────────────────

# what the form / detail files may set, and where it lives on the candidate
PROFILE_FIELDS = ("name", "current_title", "years_of_experience")
DETAIL_FIELDS = ("notice_period_days", "open_to_work", "willing_to_relocate", "location")

KEY_ALIASES = {
    "name": "name", "candidate": "name", "candidate_name": "name", "full_name": "name",
    "title": "current_title", "current_title": "current_title", "role": "current_title",
    "designation": "current_title",
    "experience": "years_of_experience", "years_of_experience": "years_of_experience",
    "yoe": "years_of_experience", "years": "years_of_experience",
    "skills": "skills",
    "notice": "notice_period_days", "notice_period": "notice_period_days",
    "notice_period_days": "notice_period_days", "notice_days": "notice_period_days",
    "open_to_work": "open_to_work", "available": "open_to_work", "looking": "open_to_work",
    "open": "open_to_work",
    "relocate": "willing_to_relocate", "willing_to_relocate": "willing_to_relocate",
    "relocation": "willing_to_relocate", "open_to_relocate": "willing_to_relocate",
    "location": "location", "city": "location", "current_location": "location",
    "expected_role": "expected_role", "desired_role": "expected_role",
}


def _key(k):
    return KEY_ALIASES.get(re.sub(r"[\s\-]+", "_", str(k).strip().lower()))


def _to_bool(v):
    if isinstance(v, bool) or v is None:
        return v
    s = str(v).strip().lower()
    if s in ("yes", "y", "true", "1", "open"):
        return True
    if s in ("no", "n", "false", "0", "closed"):
        return False
    return None


def _to_days(v):
    """'30', '30 days', '2 months', 'immediate' -> days"""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip().lower()
    if s.startswith(("immediate", "none", "serving")):
        return 0
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return None
    n = float(m.group(1))
    if "month" in s:
        n *= 30
    elif "week" in s:
        n *= 7
    return int(n)


def _to_float(v):
    try:
        return float(re.search(r"\d+(?:\.\d+)?", str(v)).group(0))
    except (AttributeError, TypeError):
        return None


def clean_edits(raw):
    """normalize keys and values from a form, JSON file, text file or CSV row"""
    out = {}
    for k, v in (raw or {}).items():
        key = _key(k)
        if key is None or v is None or (isinstance(v, str) and not v.strip()):
            continue
        if key in ("open_to_work", "willing_to_relocate"):
            v = _to_bool(v)
        elif key == "notice_period_days":
            v = _to_days(v)
        elif key == "years_of_experience":
            v = _to_float(v)
        elif key == "skills":
            v = [s.strip() for s in (v if isinstance(v, list) else str(v).split(",")) if s.strip()]
        else:
            v = str(v).strip()
        if v is not None:
            out[key] = v
    return out


def apply_edits(candidate, edits):
    """write cleaned edits onto an extracted candidate (in place) and return it"""
    e = clean_edits(edits)
    profile = candidate.setdefault("profile", {})
    for f in PROFILE_FIELDS:
        if f in e:
            profile[f] = e[f]
    if "skills" in e:
        candidate["skills"] = [{"name": s} for s in e["skills"]]
    details = dict(candidate.get("_details") or {})
    for f in DETAIL_FIELDS:
        if f in e:
            details[f] = e[f]
    if "location" in e:
        profile["location"] = e["location"]
    if "expected_role" in e:
        details["expected_role"] = e["expected_role"]
    candidate["_details"] = details
    return candidate


def summary(candidate):
    """the fields shown in the form / review list"""
    p = candidate.get("profile", {})
    d = candidate.get("_details") or {}
    return {
        "candidate_id": candidate["candidate_id"],
        "file": candidate.get("_source_file", ""),
        "name": p.get("name") or "",
        "current_title": p.get("current_title") or "",
        "years_of_experience": p.get("years_of_experience") or 0,
        "skills": [s["name"] for s in candidate.get("skills", [])],
        "location": d.get("location") or p.get("location") or "",
        "notice_period_days": d.get("notice_period_days"),
        "open_to_work": d.get("open_to_work"),
        "willing_to_relocate": d.get("willing_to_relocate"),
        "has_details": has_details(candidate),
        "details_source": candidate.get("_details_source"),
    }


# ── detail files inside a ZIP ────────────────────────────────────────────────

def _stem(path):
    return PurePosixPath(path).stem.lower()


def _parse_text_details(text):
    """'key: value' (or 'key = value') per line"""
    out = {}
    for line in text.splitlines():
        m = re.match(r"\s*([^:=]+?)\s*[:=]\s*(.+?)\s*$", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def find_detail_files(zf, resume_names):
    """
    Map resume name -> (raw details dict, source description).

    Two layouts are recognised, and can be mixed:
      * a file with the same name as the resume: asha_rao.pdf + asha_rao.txt / .json
      * one CSV for the whole ZIP with a 'file' (or 'filename' / 'resume') column
    """
    names = [n for n in zf.namelist() if not n.startswith("__") and not n.endswith("/")]
    by_stem = {}
    for n in names:
        if n.lower().endswith((".txt", ".json")):
            by_stem.setdefault(_stem(n), n)

    found = {}
    for r in resume_names:
        side = by_stem.get(_stem(r))
        if not side:
            continue
        try:
            raw = zf.read(side).decode("utf-8", errors="ignore")
            data = json.loads(raw) if side.lower().endswith(".json") else _parse_text_details(raw)
            if isinstance(data, dict) and clean_edits(data):
                found[r] = (data, PurePosixPath(side).name)
        except (ValueError, KeyError):
            pass

    for n in names:
        if not n.lower().endswith(".csv"):
            continue
        try:
            rows = csv.DictReader(io.StringIO(zf.read(n).decode("utf-8-sig", errors="ignore")))
            for row in rows:
                ref = row.get("file") or row.get("filename") or row.get("resume") or row.get("File") \
                    or row.get("Filename") or ""
                ref = _stem(ref.strip()) if ref.strip() else ""
                if not ref:
                    continue
                for r in resume_names:
                    if r not in found and _stem(r) == ref:
                        data = {k: v for k, v in row.items() if k and k.lower() not in ("file", "filename", "resume")}
                        if clean_edits(data):
                            found[r] = (data, PurePosixPath(n).name)
        except (ValueError, csv.Error):
            pass
    return found


# ── single resume: match against the job list ───────────────────────────────

JD_LIST = [
    {"id": 1,  "domain": "AI/ML",     "title": "Senior AI Engineer",        "company": "Redrob AI",      "keywords": ["embeddings", "vector database", "nlp", "llm", "python", "semantic search", "faiss", "ranking", "ndcg", "transformer"]},
    {"id": 2,  "domain": "AI/ML",     "title": "ML Platform Engineer",      "company": "FinTech Corp",   "keywords": ["mlops", "kubernetes", "pytorch", "spark", "docker", "pipeline", "infrastructure", "airflow"]},
    {"id": 3,  "domain": "AI/ML",     "title": "NLP Researcher",            "company": "AI Labs India",  "keywords": ["nlp", "bert", "transformers", "research", "publications", "language model"]},
    {"id": 4,  "domain": "Data",      "title": "Data Scientist",            "company": "Flipkart",       "keywords": ["xgboost", "sql", "analytics", "python", "statistics", "a/b testing", "pandas", "visualization"]},
    {"id": 5,  "domain": "Backend",   "title": "Backend Engineer",          "company": "Startup",        "keywords": ["python", "fastapi", "postgresql", "redis", "rest api", "docker", "microservices"]},
    {"id": 6,  "domain": "Frontend",  "title": "Frontend Developer",        "company": "SaaS Co",        "keywords": ["react", "javascript", "typescript", "css", "html", "next.js", "ui", "tailwind", "figma"]},
    {"id": 7,  "domain": "Mobile",    "title": "Android Developer",         "company": "App Studio",     "keywords": ["android", "kotlin", "java", "jetpack", "firebase", "mobile", "gradle", "xml"]},
    {"id": 8,  "domain": "Mobile",    "title": "iOS Developer",             "company": "Product Co",     "keywords": ["ios", "swift", "xcode", "swiftui", "objective-c", "apple", "mobile"]},
    {"id": 9,  "domain": "Mobile",    "title": "Flutter Developer",         "company": "Agency",         "keywords": ["flutter", "dart", "android", "ios", "firebase", "mobile", "cross-platform"]},
    {"id": 10, "domain": "DevOps",    "title": "DevOps Engineer",           "company": "Cloud Corp",     "keywords": ["docker", "kubernetes", "aws", "gcp", "azure", "ci/cd", "terraform", "jenkins", "linux", "bash"]},
    {"id": 11, "domain": "DevOps",    "title": "Cloud Architect",           "company": "Enterprise Co",  "keywords": ["aws", "gcp", "azure", "cloud", "architecture", "microservices", "terraform", "security"]},
    {"id": 12, "domain": "DevOps",    "title": "Site Reliability Engineer", "company": "Tech Giant",     "keywords": ["sre", "kubernetes", "monitoring", "prometheus", "grafana", "linux", "on-call", "reliability"]},
    {"id": 13, "domain": "Fullstack", "title": "Full Stack Developer",      "company": "Startup",        "keywords": ["react", "node.js", "python", "postgresql", "rest api", "docker", "javascript", "typescript"]},
    {"id": 14, "domain": "Data",      "title": "Data Engineer",             "company": "Analytics Co",   "keywords": ["spark", "airflow", "dbt", "sql", "python", "etl", "pipeline", "kafka", "data warehouse"]},
    {"id": 15, "domain": "Data",      "title": "Business Analyst",          "company": "Consulting",     "keywords": ["sql", "excel", "tableau", "power bi", "analytics", "requirements", "stakeholder", "data analysis"]},
    {"id": 16, "domain": "Security",  "title": "Cybersecurity Analyst",     "company": "SecureNet",      "keywords": ["security", "penetration testing", "vulnerability", "firewall", "siem", "compliance", "linux", "python"]},
    {"id": 17, "domain": "Product",   "title": "Product Manager",           "company": "Product Co",     "keywords": ["product management", "roadmap", "agile", "scrum", "user research", "metrics", "stakeholder", "jira"]},
    {"id": 18, "domain": "Design",    "title": "UI/UX Designer",            "company": "Design Studio",  "keywords": ["figma", "ui", "ux", "user research", "wireframe", "prototype", "design system", "adobe"]},
    {"id": 19, "domain": "Finance",   "title": "Financial Analyst",         "company": "Finance Corp",   "keywords": ["finance", "excel", "financial modeling", "accounting", "sql", "valuation", "reporting", "cfa"]},
    {"id": 20, "domain": "Marketing", "title": "Digital Marketing Manager", "company": "Brand Co",       "keywords": ["marketing", "seo", "content", "social media", "analytics", "campaign", "brand", "google ads"]},
]


def _role_fit(expected, jd):
    """1.0 if the role the candidate wants names this job or its domain"""
    if not expected:
        return 0.0
    e = expected.lower()
    words = [w for w in re.split(r"[\s/]+", jd["title"].lower()) if len(w) > 2 and w not in ("senior", "engineer", "developer", "manager", "analyst")]
    if contains_term(e, jd["title"].lower()) or any(contains_term(e, w) for w in words) \
            or contains_term(e, jd["domain"].lower()):
        return 1.0
    return 0.0


def match_jobs(candidate):
    p = candidate.get("profile", {})
    text = " ".join([
        p.get("headline", ""), p.get("summary", ""), p.get("current_title", ""),
        " ".join(s["name"] for s in candidate.get("skills", [])),
        " ".join(j.get("description", "") for j in candidate.get("career_history", [])[:2]),
    ]).lower()
    expected = (candidate.get("_details") or {}).get("expected_role", "")
    exp_s = experience_score(candidate)

    results = []
    for jd in JD_LIST:
        hits = [kw for kw in jd["keywords"] if contains_term(text, kw)]
        kw_score = len(hits) / len(jd["keywords"])
        role = _role_fit(expected, jd)
        # skills decide most of it; experience fit and the role they asked for nudge it
        combined = min(kw_score * 0.65 + exp_s * 0.20 + role * 0.15, 0.99)
        results.append({
            "job_id": jd["id"], "domain": jd["domain"], "job_title": jd["title"],
            "company": jd["company"], "match_score": round(combined, 3),
            "keyword_hits": len(hits), "total_keywords": len(jd["keywords"]),
            "matched_keywords": hits, "wanted_role": bool(role),
            "recommendation": "Strong match" if combined > 0.6 else "Good match" if combined > 0.4 else "Partial match",
        })
    results.sort(key=lambda x: (-x["match_score"], x["job_id"]))
    return results
