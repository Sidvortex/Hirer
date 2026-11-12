"""
extractor.py — turn a resume (PDF or image) into a structured candidate.

No LLM: regular expressions, the shared skill vocabulary in hirer_core, and
layout heuristics. Scanned PDFs and images go through Tesseract OCR; set
HIRER_OCR_LANG (for example "eng+hin") to read other languages.
"""

import os
import re
import uuid
from datetime import datetime

from hirer_core.jobs import CITIES
from hirer_core.skills import VOCAB, term_in, display

OCR_LANG = os.environ.get("HIRER_OCR_LANG", "eng")

TIER_1 = ["iit", "iim", "iisc", "bits pilani", "nit", "mit", "stanford", "harvard", "oxford", "cambridge", "cmu",
           "iit bombay", "iit delhi", "iit madras", "iit kanpur", "iit kharagpur", "iit roorkee", "iit guwahati"]
TIER_2 = ["vit", "manipal", "srm", "amity", "symbiosis", "pec", "thapar", "dtu", "nsut",
           "iiit hyderabad", "iiit bangalore", "iiit delhi", "jadavpur", "anna university"]
TIER_3 = ["muit", "galgotias", "gl bajaj", "hbtu", "aktu", "mtu", "sharda", "bennett",
           "lovely professional", "lpu", "maharishi"]


def _contains_term(text: str, term: str) -> bool:
    """Whole-word match, so 'mit' doesn't hit 'submit', 'rag' doesn't hit 'average', 'excel' doesn't hit 'excellent'."""
    return re.search(r'(?<![a-z0-9])' + re.escape(term) + r'(?![a-z0-9])', text) is not None


def _column_split(page):
    """
    If the page has two columns, return (x, header_bottom): the x position of
    the gap between them, and where a full-width header (name, contact line)
    ends. Returns None for an ordinary single-column page.
    """
    words = page.extract_words()
    if len(words) < 40:
        return None
    x0, top, x1, bottom = page.bbox
    width, height = x1 - x0, bottom - top
    gap = 5          # half-width of the empty band a column gap must have
    valid = {}
    x = x0 + 0.2 * width
    while x < x0 + 0.8 * width:
        crossing = [w for w in words if w["x0"] < x + gap and w["x1"] > x - gap]
        header = max((w["bottom"] for w in crossing), default=top)
        if len(crossing) <= 0.15 * len(words) and header <= top + 0.3 * height:
            body = [w for w in words if w["top"] >= header]
            left = sum(w["x1"] <= x for w in body)
            if body and min(left, len(body) - left) >= 0.15 * len(body):
                valid[round(x, 1)] = header
        x += 3
    if not valid:
        return None
    # centre of the widest run of valid positions
    xs = sorted(valid)
    runs, run = [], [xs[0]]
    for v in xs[1:]:
        if v - run[-1] <= 3.5:
            run.append(v)
        else:
            runs.append(run)
            run = [v]
    runs.append(run)
    best = max(runs, key=len)
    mid = best[len(best) // 2]
    return mid, valid[mid]


def _page_text(page):
    """text of one page, reading a two-column layout one column at a time"""
    split = _column_split(page)
    if split is None:
        return page.extract_text() or ""
    x, header_bottom = split
    x0, top, x1, bottom = page.bbox
    parts = [page.crop((x0, top, x1, header_bottom)).extract_text() or ""] if header_bottom > top + 1 else []
    # within_bbox keeps only text fully inside the box, so the header's last line isn't read twice
    parts += [page.within_bbox(b).extract_text() or ""
              for b in ((x0, header_bottom, x, bottom), (x, header_bottom, x1, bottom))]
    return "\n".join(p for p in parts if p.strip())


def extract_text_from_pdf(pdf_path: str) -> str:
    """pdfplumber first (column-aware), OCR if the PDF has no text layer"""
    text, links = "", []
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            pages = []
            for page in pdf.pages:
                pages.append(_page_text(page))
                links += [h.get("uri") for h in page.hyperlinks if h.get("uri")]
            text = "\n".join(pages)
    except Exception:
        pass

    if text.strip():
        # links hidden behind words like "GitHub" are part of the resume too
        hidden = [u for u in dict.fromkeys(links) if u not in text]
        return text + ("\n" + "\n".join(hidden) if hidden else "")

    try:
        import pytesseract
        from pdf2image import convert_from_path
        text = "\n".join(pytesseract.image_to_string(page, lang=OCR_LANG)
                         for page in convert_from_path(pdf_path, dpi=200))
    except Exception:
        pass
    return text


def extract_text_from_image(image_path: str) -> str:
    """OCR on an image upload. Returns "" if Tesseract isn't installed, so the caller can say so."""
    try:
        import pytesseract
        from PIL import Image
        return pytesseract.image_to_string(Image.open(image_path), lang=OCR_LANG)
    except Exception:
        return ""


def extract_from_text(text: str, filename: str = "resume") -> dict:
    text_lower = text.lower()
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    candidate_id = f"CAND_{str(uuid.uuid4())[:8].upper()}"
    career = _extract_career(text, lines)
    return {
        "candidate_id": candidate_id,
        "profile": _extract_profile(text, text_lower, lines, career),
        "skills": _extract_skills(text_lower),
        "career_history": career,
        "education": _extract_education(text, text_lower, lines),
        "certifications": _extract_certifications(text_lower),
        "redrob_signals": _default_signals(),
        "_source_file": filename,
    }


def _extract_profile(text, text_lower, lines, career):
    return {
        "name": _extract_name(lines),
        "email": _extract_email(text),
        "phone": _extract_phone(text),
        "headline": _extract_headline(lines),
        "summary": _extract_summary(text_lower, lines),
        "current_title": _extract_current_title(lines, text_lower),
        "years_of_experience": _extract_yoe(text_lower, career),
        "location": _extract_location(text_lower),
        "current_industry": _infer_industry(text_lower),
        "github": _extract_github(text),
    }


def _extract_github(text):
    m = re.search(r'github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))', text, re.I)
    return m.group(1) if m and m.group(1).lower() not in ("orgs", "topics", "features") else None


def _extract_name(lines):
    for line in lines[:4]:
        skip = ["resume", "cv", "curriculum", "profile", "portfolio", "contact", "summary", "skills",
                "experience", "education", "projects", "objective", "languages", "certifications"]
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


def _extract_yoe(text_lower, career):
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
    return _calc_yoe_from_career(career)


def _calc_yoe_from_career(career):
    """Years actually worked: job spans added up, overlaps counted once, gaps not counted."""
    now = datetime.now().year
    spans = sorted((j["start_year"], max(j["start_year"], min(j.get("end_year") or now, now)))
                   for j in career if j.get("start_year") and 1970 <= j["start_year"] <= now)
    merged = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    # a job that starts and ends in the same year still counts as half a year
    return float(sum(max(end - start, 0.5) for start, end in merged))


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
    for city in CITIES:
        if _contains_term(text_lower, city):
            return city.title()
    return ""


def _infer_industry(text_lower):
    groups = [
        ("Artificial Intelligence", ["machine learning", "nlp", "ai", "deep learning", "llm"]),
        ("Data Engineering", ["data engineer", "spark", "airflow", "etl", "kafka"]),
        ("Frontend Development", ["frontend", "react", "vue", "angular", "ui/ux"]),
        ("Backend Development", ["backend", "fastapi", "django", "flask", "node.js"]),
        ("DevOps / Cloud", ["devops", "kubernetes", "docker", "cloud", "aws", "gcp"]),
        ("Data Science", ["data science", "analytics", "tableau", "power bi"]),
        ("Mobile Development", ["android", "ios", "flutter", "react native"]),
        ("Finance", ["finance", "accounting", "financial"]),
        ("Marketing", ["marketing", "seo", "content", "brand"]),
        ("Software Engineering", ["software", "developer", "engineer"]),
    ]
    # whole words only ("ai" must not match "email"); the group with the most hits wins
    hits = [(sum(_contains_term(text_lower, w) for w in words), name) for name, words in groups]
    best = max(hits, key=lambda h: h[0])
    return best[1] if best[0] else "Technology"


def _extract_skills(text_lower):
    found = []
    for skill in VOCAB:
        if not term_in(text_lower, skill):
            continue
        proficiency = "intermediate"
        if any(w in text_lower for w in [f"expert in {skill}", f"proficient in {skill}", f"strong {skill}"]):
            proficiency = "expert"
        elif any(w in text_lower for w in [f"learning {skill}", f"basic {skill}"]):
            proficiency = "beginner"
        found.append({"name": display(skill), "proficiency": proficiency, "duration_months": None, "endorsements": 0})
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
            if current_job:
                current_job["description"] = " ".join(desc_lines[:5])
                career.append(current_job)
            years = re.findall(r'(?:19|20)\d{2}', line)
            # "ML Engineer, Acme 2018 - Present": the text before the year is title and company
            lead = re.split(r'(?i)[\s(|–—-]*(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+)?(?:19|20)\d{2}',
                            line)[0].strip(" ,|–—-")
            lead_parts = [x.strip() for x in re.split(r'\s*[,|@]\s*|\s+at\s+', lead) if x.strip()]
            current_job = {
                "title": lead_parts[0] if lead_parts else "",
                "company": lead_parts[1] if len(lead_parts) > 1 else "",
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
    if current_job:
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
            seg = "\n".join(text[m.start():].split("\n")[:2])
            years = sorted(int(y) for y in re.findall(r'(?:19|20)\d{2}', seg))
            edu.append({
                "degree": degree_name,
                "field_of_study": _extract_field(context),
                "institution": institution,
                "tier": tier,
                "start_year": years[0] if years else None,
                "end_year": years[-1] if len(years) >= 2 else None,
                "grade": _extract_grade(seg.lower()),
            })
            if len(edu) >= 3:
                break
    return edu


def _find_institution(context):
    for inst in sorted(TIER_1 + TIER_2 + TIER_3, key=len, reverse=True):
        if _contains_term(context, inst):
            return _pretty_institution(inst)
    m = re.search(r'([a-z\s]+(?:university|college|institute|school)[a-z\s]*)', context)
    if m:
        return m.group(0).strip().title()[:50]
    return "Unknown Institution"


_ACRONYMS = {"iit", "iim", "iisc", "bits", "nit", "mit", "cmu", "vit", "srm", "pec", "dtu",
             "nsut", "iiit", "hbtu", "aktu", "mtu", "lpu", "muit", "gl"}


def _pretty_institution(inst):
    return " ".join(w.upper() if w in _ACRONYMS else w.title() for w in inst.split())


def _get_tier(context):
    for inst in sorted(TIER_1 + TIER_2 + TIER_3, key=len, reverse=True):
        if _contains_term(context, inst):
            return "tier_1" if inst in TIER_1 else "tier_2" if inst in TIER_2 else "tier_3"
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


def _extract_grade(segment):
    m = (re.search(r'(?:cgpa|gpa|cpi)\s*[:\-]?\s*(\d+(?:\.\d+)?)', segment)
         or re.search(r'(\d+(?:\.\d+)?)\s*(?:cgpa|gpa|cpi)', segment))
    if m: return f"{m.group(1)} CGPA"
    m = re.search(r'(\d+(?:\.\d+)?)\s*%', segment)
    if m: return f"{m.group(1)}%"
    return None


def _extract_certifications(text_lower):
    certs = []
    cert_kws = ["aws certified", "google cloud certified", "azure certified", "gcp certified",
                "tensorflow certificate", "deep learning specialization", "nlp specialization",
                "certified kubernetes", "pmp", "cfa"]
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
