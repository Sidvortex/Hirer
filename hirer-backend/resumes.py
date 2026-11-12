"""
Helpers for the resume modes: applying a person's edits to an extracted
resume, reading detail files that sit next to resumes in a ZIP, checking a
GitHub link, and matching a single resume against the job list.
"""

import csv
import io
import json
import os
import re
import urllib.request
from pathlib import PurePosixPath

from hirer_core.features import experience_score, full_text, has_details
from hirer_core.jobs import PRESETS
from hirer_core.skills import term_in
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
        "github": candidate.get("_github"),
    }


def github_summary(username, timeout=5):
    """
    Public facts about a GitHub account named on a resume, or None.
    Off unless HIRER_VERIFY_GITHUB=1. Set GITHUB_TOKEN for a higher request limit
    (without one GitHub allows about 60 lookups an hour).
    """
    if os.environ.get("HIRER_VERIFY_GITHUB") != "1" or not username:
        return None
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "hirer"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    try:
        req = urllib.request.Request(f"https://api.github.com/users/{username}", headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        return {"username": data["login"], "public_repos": data["public_repos"],
                "followers": data["followers"], "last_active": (data.get("updated_at") or "")[:10]}
    except Exception:
        return None       # a failed lookup must never block reading the resume


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

_GENERIC = {"senior", "engineer", "developer", "manager", "analyst"}


def _role_fit(expected, job):
    """1.0 if the role the candidate wants names this job or its domain"""
    if not expected:
        return 0.0
    e = expected.lower()
    words = [w for w in re.split(r"[\s/]+", job.title.lower()) if len(w) > 2 and w not in _GENERIC]
    if contains_term(e, job.title.lower()) or any(contains_term(e, w) for w in words) \
            or contains_term(e, job.domain.lower()):
        return 1.0
    return 0.0


def match_jobs(candidate):
    text = full_text(candidate)
    expected = (candidate.get("_details") or {}).get("expected_role", "")

    results = []
    for job in PRESETS:
        # the built-in job has a long must-have list; its ten headline skills are a fairer yardstick
        keywords = job.must_have if job.id != 1 else [
            "embedding", "vector database", "nlp", "llm", "python", "semantic search", "faiss",
            "ranking", "ndcg", "transformer"]
        hits = [kw for kw in keywords if term_in(text, kw)]
        kw_score = len(hits) / len(keywords)
        role = _role_fit(expected, job)
        # skills decide most of it; experience fit and the role they asked for nudge it
        combined = min(kw_score * 0.65 + experience_score(candidate, job) * 0.20 + role * 0.15, 0.99)
        results.append({
            "job_id": job.id, "domain": job.domain, "job_title": job.title,
            "company": job.company, "match_score": round(combined, 3),
            "keyword_hits": len(hits), "total_keywords": len(keywords),
            "matched_keywords": hits, "wanted_role": bool(role),
            "recommendation": "Strong match" if combined > 0.6 else "Good match" if combined > 0.4 else "Partial match",
        })
    results.sort(key=lambda x: (-x["match_score"], x["job_id"]))
    return results
