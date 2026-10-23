"""
Hirer Backend — FastAPI server wrapping the ranking pipeline

NOTE: Previously this used Server-Sent Events (StreamingResponse) to push
progress to the frontend. That broke on Railway because Railway's proxy
buffers the response instead of flushing it chunk-by-chunk, so the events
never reached the browser (works fine locally, hangs forever in prod).

Fix: switch to a polling model.
  1. POST /rank        -> validates input, kicks off the job in the
                           background, returns {job_id} immediately.
  2. GET  /status/{id}  -> frontend polls this every ~1s for progress.
  3. GET  /preview/{id} -> once status == "done", fetch the results.
  4. GET  /download/{id}-> download the ranked CSV.

No long-lived HTTP response is held open, so there's nothing for a proxy
to buffer.
"""

import os
import sys
import json
import uuid
import tempfile
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

# this folder (for extractor.py) and the repo root (for the shared hirer_core package)
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))

from hirer_core import rank                                   # noqa: E402
from hirer_core.jd import JD_TITLE                            # noqa: E402
from hirer_core.utils import load_candidates, contains_term   # noqa: E402

CSV_COLUMNS = ["candidate_id", "rank", "score", "reasoning"]

app = FastAPI(title="Hirer API")

# Allowed frontend origins. Always allow local dev; additionally allow the
# deployed Vercel frontend via FRONTEND_URL (comma-separated if you have more
# than one, e.g. a preview + production URL).
_default_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
_extra_origins = [o.strip() for o in os.environ.get("FRONTEND_URL", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# temp storage for jobs
JOBS: dict[str, dict] = {}
TEMP_DIR = Path(tempfile.gettempdir()) / "hirer"
TEMP_DIR.mkdir(exist_ok=True)

# Live-server limits. 0 means "no limit", which is the default for local runs.
# Set these as environment variables on the hosted backend (the Dockerfile does).
JSONL_ENTRY_LIMIT = int(os.environ.get("JSONL_ENTRY_LIMIT", "0"))
PDF_COUNT_LIMIT   = int(os.environ.get("PDF_COUNT_LIMIT", "0"))
PDF_SIZE_LIMIT_MB = float(os.environ.get("PDF_SIZE_LIMIT_MB", "0"))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/rank")
async def rank_candidates(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    skill_weight: float = Form(0.40),
    semantic_weight: float = Form(0.35),
    behavioral_weight: float = Form(0.25),
    top_n: int = Form(100),
    use_semantic: bool = Form(False),
):
    """
    Upload a candidates.jsonl file, kick off ranking in the background,
    and immediately return a job_id. Poll GET /status/{job_id} for progress.
    """
    # validate weights
    total = round(skill_weight + semantic_weight + behavioral_weight, 2)
    if abs(total - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail=f"Weights must sum to 1.0, got {total}")

    # validate file type
    if not file.filename or not file.filename.endswith((".jsonl", ".json")):
        raise HTTPException(status_code=400, detail="File must be .jsonl or .json")

    # save uploaded file
    job_id = str(uuid.uuid4())
    job_dir = TEMP_DIR / job_id
    job_dir.mkdir()

    input_path = job_dir / "candidates.jsonl"
    output_path = job_dir / "submission.csv"

    with open(input_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    if JSONL_ENTRY_LIMIT:
        with open(input_path, "rb") as f:
            n_entries = sum(1 for line in f if line.strip())
        if n_entries > JSONL_ENTRY_LIMIT:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise HTTPException(
                status_code=400,
                detail=f"This server accepts up to {JSONL_ENTRY_LIMIT:,} entries per file; yours has "
                       f"{n_entries:,}. Run Hirer locally for larger files.",
            )

    JOBS[job_id] = {
        "status": "running",
        "step": "Queued...",
        "pct": 0,
        "steps": [],
        "input": str(input_path),
        "output": str(output_path),
        "weights": (skill_weight, semantic_weight, behavioral_weight),
        "top_n": top_n,
        "use_semantic": use_semantic,
        "error": None,
        "result": None,
    }

    background_tasks.add_task(
        run_ranking_job,
        job_id,
        str(input_path),
        str(output_path),
        skill_weight,
        semantic_weight,
        behavioral_weight,
        top_n,
        use_semantic,
    )

    return {"job_id": job_id, "status": "running"}


def _update(job_id: str, step: str, pct: int):
    """helper to push a progress update into the job dict"""
    job = JOBS.get(job_id)
    if not job:
        return
    job["step"] = step
    job["pct"] = pct
    job["steps"].append(step)


def _finish(job_id: str, result: dict, output_path: str, csv_columns: list[str]):
    """write the CSV and the full JSON rows, mark the job done"""
    import pandas as pd

    rows = result["rows"]
    pd.DataFrame(rows, columns=list(rows[0].keys()) if rows else csv_columns)[csv_columns] \
        .to_csv(output_path, index=False)
    with open(Path(output_path).with_suffix(".json"), "w") as f:
        json.dump(rows, f)

    JOBS[job_id].update({"status": "done", "pct": 100, "step": "Done!"})
    JOBS[job_id]["steps"].append("Done!")
    JOBS[job_id]["result"] = {
        "job_id": job_id,
        "total_candidates": result["total_candidates"],
        "ranked": len(rows),
        "top_candidate": rows[0]["candidate_id"] if rows else None,
        "top_score": rows[0]["score"] if rows else None,
        "weights_used": result["weights_used"],
        "reference_date": result["reference_date"],
        "job_title": JD_TITLE,
    }


def run_ranking_job(
    job_id: str,
    input_path: str,
    output_path: str,
    skill_weight: float,
    semantic_weight: float,
    behavioral_weight: float,
    top_n: int,
    use_semantic: bool,
):
    """Runs the full ranking pipeline in the background;
    the frontend follows progress by polling /status/{job_id}."""
    try:
        _update(job_id, "Loading candidates...", 10)
        candidates = load_candidates(input_path)
        _update(job_id, f"Loaded {len(candidates):,} candidates", 20)

        result = rank(
            candidates,
            {"skill": skill_weight, "semantic": semantic_weight, "behavioral": behavioral_weight},
            use_semantic=use_semantic,
            top_n=top_n,
            progress=lambda step, pct: _update(job_id, step, pct),
        )
        _finish(job_id, result, output_path, CSV_COLUMNS)

    except Exception as e:
        JOBS[job_id].update({"status": "error", "error": str(e), "step": f"Error: {e}"})


@app.get("/status/{job_id}")
def get_status(job_id: str):
    """Poll this for progress. status is 'running' | 'done' | 'error'."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job_id,
        "status": job["status"],
        "step": job["step"],
        "pct": job["pct"],
        "steps": job["steps"],
        "error": job["error"],
        "result": job["result"],
    }


@app.get("/download/{job_id}")
def download_result(job_id: str):
    """Download the ranked CSV for a completed job"""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail=f"Job status: {job['status']}")
    output_path = job["output"]
    if not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="Output file not found")
    return FileResponse(
        output_path,
        media_type="text/csv",
        filename="submission.csv",
    )


@app.get("/preview/{job_id}")
def preview_result(job_id: str, limit: int = 20):
    """Preview top N results as JSON"""
    job = JOBS.get(job_id)
    if not job or job["status"] != "done":
        raise HTTPException(status_code=404, detail="Job not found or not complete")
    rows_path = Path(job["output"]).with_suffix(".json")
    if rows_path.exists():
        with open(rows_path) as f:
            rows = json.load(f)
    else:
        import pandas as pd
        rows = pd.read_csv(job["output"]).to_dict(orient="records")
    return {"results": rows[:limit], "meta": job.get("result")}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)




# ── Single PDF / Image resume screening ────────────────────────────────────────
@app.post("/screen-single")
async def screen_single_resume(file: UploadFile = File(...)):
    """Upload 1 PDF or image resume → get best job matches."""
    fname = (file.filename or "").lower()
    is_pdf   = fname.endswith(".pdf")
    is_image = fname.endswith((".jpg", ".jpeg", ".png", ".webp"))

    if not (is_pdf or is_image):
        raise HTTPException(status_code=400, detail="File must be a PDF or image (JPG/PNG)")

    try:
        from extractor import extract_from_text, extract_text_from_pdf, extract_text_from_image
        from hirer_core.features import experience_score
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Missing dependency: {e}")

    contents = await file.read()
    job_dir  = TEMP_DIR / str(uuid.uuid4())
    job_dir.mkdir()
    file_path = job_dir / (file.filename or "resume")
    with open(file_path, "wb") as f:
        f.write(contents)

    if is_pdf:
        text = extract_text_from_pdf(str(file_path))
    else:
        text = extract_text_from_image(str(file_path))

    if not text.strip():
        if is_image:
            raise HTTPException(
                status_code=422,
                detail="Image/scanned resume OCR is not available on the live server. Please convert your resume to a text-based PDF and upload that instead."
            )
        raise HTTPException(
            status_code=422,
            detail="Could not extract text from this PDF. It may be a scanned image. Please use a text-based PDF (one where you can select/copy text)."
        )

    candidate = extract_from_text(text, file.filename or "resume")

    # Extended job descriptions for resume mode
    JD_LIST = [
        # AI / ML
        {"id":1,  "domain":"AI/ML",       "title":"Senior AI Engineer",        "company":"Redrob AI",          "keywords":["embeddings","vector database","nlp","llm","python","semantic search","faiss","ranking","ndcg","transformer"]},
        {"id":2,  "domain":"AI/ML",       "title":"ML Platform Engineer",      "company":"FinTech Corp",        "keywords":["mlops","kubernetes","pytorch","spark","docker","pipeline","infrastructure","airflow"]},
        {"id":3,  "domain":"AI/ML",       "title":"NLP Researcher",            "company":"AI Labs India",       "keywords":["nlp","bert","transformers","research","publications","language model"]},
        {"id":4,  "domain":"Data",        "title":"Data Scientist",            "company":"Flipkart",            "keywords":["xgboost","sql","analytics","python","statistics","a/b testing","pandas","visualization"]},
        {"id":5,  "domain":"Backend",     "title":"Backend Engineer",          "company":"Startup",             "keywords":["python","fastapi","postgresql","redis","rest api","docker","microservices"]},
        # Frontend / Mobile
        {"id":6,  "domain":"Frontend",    "title":"Frontend Developer",        "company":"SaaS Co",             "keywords":["react","javascript","typescript","css","html","next.js","ui","tailwind","figma"]},
        {"id":7,  "domain":"Mobile",      "title":"Android Developer",         "company":"App Studio",          "keywords":["android","kotlin","java","jetpack","firebase","mobile","gradle","xml"]},
        {"id":8,  "domain":"Mobile",      "title":"iOS Developer",             "company":"Product Co",          "keywords":["ios","swift","xcode","swiftui","objective-c","apple","mobile"]},
        {"id":9,  "domain":"Mobile",      "title":"Flutter Developer",         "company":"Agency",              "keywords":["flutter","dart","android","ios","firebase","mobile","cross-platform"]},
        # DevOps / Cloud
        {"id":10, "domain":"DevOps",      "title":"DevOps Engineer",           "company":"Cloud Corp",          "keywords":["docker","kubernetes","aws","gcp","azure","ci/cd","terraform","jenkins","linux","bash"]},
        {"id":11, "domain":"DevOps",      "title":"Cloud Architect",           "company":"Enterprise Co",       "keywords":["aws","gcp","azure","cloud","architecture","microservices","terraform","security"]},
        {"id":12, "domain":"DevOps",      "title":"Site Reliability Engineer", "company":"Tech Giant",          "keywords":["sre","kubernetes","monitoring","prometheus","grafana","linux","on-call","reliability"]},
        # Full Stack
        {"id":13, "domain":"Fullstack",   "title":"Full Stack Developer",      "company":"Startup",             "keywords":["react","node.js","python","postgresql","rest api","docker","javascript","typescript"]},
        # Data Engineering
        {"id":14, "domain":"Data",        "title":"Data Engineer",             "company":"Analytics Co",        "keywords":["spark","airflow","dbt","sql","python","etl","pipeline","kafka","data warehouse"]},
        {"id":15, "domain":"Data",        "title":"Business Analyst",          "company":"Consulting",          "keywords":["sql","excel","tableau","power bi","analytics","requirements","stakeholder","data analysis"]},
        # Cybersecurity
        {"id":16, "domain":"Security",    "title":"Cybersecurity Analyst",     "company":"SecureNet",           "keywords":["security","penetration testing","vulnerability","firewall","siem","compliance","linux","python"]},
        # Product / Design
        {"id":17, "domain":"Product",     "title":"Product Manager",           "company":"Product Co",          "keywords":["product management","roadmap","agile","scrum","user research","metrics","stakeholder","jira"]},
        {"id":18, "domain":"Design",      "title":"UI/UX Designer",            "company":"Design Studio",       "keywords":["figma","ui","ux","user research","wireframe","prototype","design system","adobe"]},
        # Finance / Non-tech
        {"id":19, "domain":"Finance",     "title":"Financial Analyst",         "company":"Finance Corp",        "keywords":["finance","excel","financial modeling","accounting","sql","valuation","reporting","cfa"]},
        {"id":20, "domain":"Marketing",   "title":"Digital Marketing Manager", "company":"Brand Co",            "keywords":["marketing","seo","content","social media","analytics","campaign","brand","google ads"]},
    ]

    import numpy as np
    candidate_text = " ".join([
        candidate["profile"].get("headline", ""),
        candidate["profile"].get("summary", ""),
        candidate["profile"].get("current_title", ""),
        " ".join(s["name"].lower() for s in candidate.get("skills", [])),
        " ".join(j.get("description", "") for j in candidate.get("career_history", [])[:2]),
    ]).lower()

    results = []
    for jd in JD_LIST:
        kw_hits = sum(1 for kw in jd["keywords"] if contains_term(candidate_text, kw))
        kw_score = kw_hits / len(jd["keywords"])
        exp_s = experience_score(candidate)
        combined = min(kw_score * 0.65 + exp_s * 0.25 + 0.10, 0.99)
        results.append({
            "job_id":         jd["id"],
            "domain":         jd["domain"],
            "job_title":      jd["title"],
            "company":        jd["company"],
            "match_score":    round(combined, 3),
            "keyword_hits":   kw_hits,
            "total_keywords": len(jd["keywords"]),
            "recommendation": "Strong match" if combined > 0.6 else "Good match" if combined > 0.4 else "Partial match",
        })

    results.sort(key=lambda x: -x["match_score"])

    return {
        "candidate": {
            "name":                candidate["profile"]["name"],
            "current_title":       candidate["profile"]["current_title"],
            "years_of_experience": candidate["profile"]["years_of_experience"],
            "skills_found":        [s["name"] for s in candidate["skills"][:12]],
            "location":            candidate["profile"]["location"],
            "industry":            candidate["profile"]["current_industry"],
        },
        "job_matches": results,
        "best_match":  results[0]["job_title"] if results else None,
        "top_domain":  results[0]["domain"]    if results else None,
    }


# ── Bulk PDF ZIP screening ──────────────────────────────────────────────────────
@app.post("/screen-bulk")
async def screen_bulk_resumes(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    skill_weight:      float = Form(0.40),
    semantic_weight:   float = Form(0.35),
    behavioral_weight: float = Form(0.25),
    top_n:             int   = Form(50),
    use_semantic:      bool  = Form(False),
):
    """Upload a ZIP of PDF/image resumes → extract → rank. Poll /status/{job_id}."""
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a .zip")

    total_w = round(skill_weight + semantic_weight + behavioral_weight, 2)
    if abs(total_w - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail=f"Weights must sum to 1.0, got {total_w}")

    contents = await file.read()
    size_mb  = len(contents) / (1024 * 1024)
    if PDF_SIZE_LIMIT_MB and size_mb > PDF_SIZE_LIMIT_MB:
        raise HTTPException(status_code=400, detail=f"ZIP too large ({size_mb:.1f} MB). Live limit is {PDF_SIZE_LIMIT_MB} MB.")

    job_id      = str(uuid.uuid4())
    job_dir     = TEMP_DIR / job_id
    job_dir.mkdir()
    zip_path    = job_dir / "resumes.zip"
    output_path = job_dir / "submission.csv"

    with open(zip_path, "wb") as f:
        f.write(contents)

    JOBS[job_id] = {"status": "running", "step": "Queued...", "pct": 0, "steps": [],
                    "output": str(output_path), "total_candidates": 0, "error": None, "result": None}

    background_tasks.add_task(
        _run_bulk_pdf,
        job_id, str(zip_path), str(output_path),
        skill_weight, semantic_weight, behavioral_weight, top_n, use_semantic
    )
    return {"job_id": job_id, "status": "running"}


def _upd(job_id, step, pct, status="running"):
    if job_id in JOBS:
        JOBS[job_id].update({"step": step, "pct": pct, "status": status})
        JOBS[job_id]["steps"].append(step)


def _run_bulk_pdf(job_id, zip_path, output_path, w1, w2, w3, top_n, use_semantic=False):
    try:
        import zipfile
        from extractor import extract_from_text, extract_text_from_pdf, extract_text_from_image

        _upd(job_id, "Opening ZIP...", 5)

        SUPPORTED = (".pdf", ".jpg", ".jpeg", ".png", ".webp")
        candidates = []

        with zipfile.ZipFile(zip_path, "r") as z:
            files = [f for f in z.namelist()
                     if f.lower().endswith(SUPPORTED) and not f.startswith("__")]

            if PDF_COUNT_LIMIT and len(files) > PDF_COUNT_LIMIT:
                files = files[:PDF_COUNT_LIMIT]
                _upd(job_id, f"Capped to {PDF_COUNT_LIMIT} files (live server limit)", 6)

            JOBS[job_id]["total_candidates"] = len(files)
            tmp = Path(zip_path).parent / "files"
            tmp.mkdir(exist_ok=True)

            for i, fname in enumerate(files):
                try:
                    fpath = tmp / f"{i}{Path(fname).suffix}"
                    with open(fpath, "wb") as f:
                        f.write(z.read(fname))
                    if fname.lower().endswith(".pdf"):
                        text = extract_text_from_pdf(str(fpath))
                    else:
                        text = extract_text_from_image(str(fpath))
                    if text.strip():
                        candidates.append(extract_from_text(text, fname))
                except Exception:
                    pass
                _upd(job_id, f"Extracted {i+1}/{len(files)} files...", 5 + int(((i + 1) / len(files)) * 20))

        if not candidates:
            raise ValueError("Could not extract text from any file.")

        _upd(job_id, f"Extracted {len(candidates)} resumes. Scoring...", 28)
        # Resumes carry no platform activity data, so every candidate gets the
        # same behavioral score; rank() notices that and moves its weight to
        # the components that actually differ between candidates.
        result = rank(
            candidates,
            {"skill": w1, "semantic": w2, "behavioral": w3},
            use_semantic=use_semantic,
            top_n=top_n,
            progress=lambda step, pct: _upd(job_id, step, pct),
        )
        _finish(job_id, result, output_path, ["candidate_id", "name", "rank", "score", "reasoning", "source_file"])

    except Exception as e:
        JOBS[job_id].update({"status": "error", "error": str(e), "step": f"Error: {e}"})
