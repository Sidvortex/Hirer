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
import uuid
import asyncio
import tempfile
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

# add current dir to path so ranking.py imports work
sys.path.insert(0, os.path.dirname(__file__))

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


async def run_ranking_job(
    job_id: str,
    input_path: str,
    output_path: str,
    skill_weight: float,
    semantic_weight: float,
    behavioral_weight: float,
    top_n: int,
    use_semantic: bool,
):
    """Runs the full ranking pipeline. Executes in the background;
    frontend finds out how it's going by polling /status/{job_id}."""
    try:
        _update(job_id, "Loading candidates...", 10)
        await asyncio.sleep(0)

        from utils import load_candidates, normalize_0_1, build_candidate_text
        from feature_engineering import get_features, MUST_HAVE_SKILLS, _get_full_text

        candidates = load_candidates(input_path)
        _update(job_id, f"Loaded {len(candidates):,} candidates", 20)
        await asyncio.sleep(0)

        import numpy as np
        import pandas as pd

        _update(job_id, "Computing keyword scores...", 30)

        feature_rows = [get_features(c) for c in candidates]
        feat_df = pd.DataFrame(feature_rows)
        combined_skill = (
            feat_df["skill_score"] * 0.5 +
            feat_df["experience_score"] * 0.25 +
            feat_df["title_score"] * 0.15 +
            feat_df["education_score"] * 0.10
        )

        _update(job_id, "Keyword scores done", 45)
        await asyncio.sleep(0)

        # semantic scores
        if use_semantic:
            _update(job_id, "Loading sentence-transformer model...", 50)
            await asyncio.sleep(0)

            from sentence_transformers import SentenceTransformer
            from sklearn.metrics.pairwise import cosine_similarity

            JD_TEXT = """Senior AI Engineer at Redrob AI. Requirements: embeddings, sentence-transformers,
            vector databases, FAISS, Pinecone, Qdrant, Python, NDCG, MRR, semantic search, NLP, LLM fine-tuning.
            5-9 years experience. Pune or Noida India."""

            model = SentenceTransformer("all-MiniLM-L6-v2")
            jd_emb = model.encode([JD_TEXT])

            _update(job_id, "Encoding candidates...", 60)
            texts = [build_candidate_text(c) for c in candidates]

            all_embs = []
            batch_size = 64
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                emb = model.encode(batch, show_progress_bar=False)
                all_embs.append(emb)
                pct = 60 + int((i / len(texts)) * 20)
                _update(job_id, f"Encoding... {i}/{len(texts)}", pct)
                await asyncio.sleep(0)

            all_embs_np = np.vstack(all_embs)
            semantic_scores = cosine_similarity(jd_emb, all_embs_np)[0].tolist()
        else:
            semantic_scores = [0.5] * len(candidates)

        _update(job_id, "Computing behavioral signals...", 78)
        await asyncio.sleep(0)

        behavioral_arr = feat_df["behavioral_score"].values
        semantic_arr = np.array(semantic_scores)

        _update(job_id, "Combining weighted scores...", 85)
        final_scores = (
            skill_weight * normalize_0_1(combined_skill.values) +
            semantic_weight * normalize_0_1(semantic_arr) +
            behavioral_weight * normalize_0_1(behavioral_arr)
        )

        sorted_idx = np.argsort(-final_scores)
        top_idx = sorted_idx[:top_n]

        _update(job_id, f"Ranking top {top_n} candidates...", 92)
        await asyncio.sleep(0)

        rows = []
        for rank, idx in enumerate(top_idx, start=1):
            c = candidates[idx]
            text = _get_full_text(c).lower()
            skill_hits = sum(1 for kw in MUST_HAVE_SKILLS if kw in text)
            sig = c.get("redrob_signals", {})
            p = c.get("profile", {})

            parts = [f"{p.get('current_title', '?')} with {p.get('years_of_experience', 0):.1f} yrs exp"]
            parts.append(f"{skill_hits} JD skill matches")
            if sig.get("open_to_work_flag"):
                parts.append("open to work")
            if sig.get("github_activity_score", -1) > 50:
                parts.append(f"GitHub {sig['github_activity_score']:.0f}")
            if sig.get("recruiter_response_rate", 0) > 0.7:
                parts.append(f"RR {sig['recruiter_response_rate']:.2f}")

            rows.append({
                "candidate_id": c["candidate_id"],
                "rank": rank,
                "score": round(float(final_scores[idx]), 4),
                "reasoning": "; ".join(parts) + ".",
            })

        out_df = pd.DataFrame(rows)
        out_df.to_csv(output_path, index=False)

        JOBS[job_id]["status"] = "done"
        JOBS[job_id]["pct"] = 100
        JOBS[job_id]["step"] = "Done!"
        JOBS[job_id]["steps"].append("Done!")
        JOBS[job_id]["result"] = {
            "job_id": job_id,
            "total_candidates": len(candidates),
            "ranked": len(rows),
            "top_candidate": rows[0]["candidate_id"] if rows else None,
            "top_score": rows[0]["score"] if rows else None,
        }

    except Exception as e:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"] = str(e)


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
    import pandas as pd
    df = pd.read_csv(job["output"])
    return {"results": df.head(limit).to_dict(orient="records")}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


# ── Limits ─────────────────────────────────────────────────────────────────────
JSONL_ENTRY_LIMIT = 1000
PDF_COUNT_LIMIT   = 50
PDF_SIZE_LIMIT_MB = 50


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
        from feature_engineering import experience_score
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
        raise HTTPException(status_code=400, detail="Could not extract text. If this is a scanned PDF, make sure Tesseract is installed on the server.")

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
        kw_hits = sum(1 for kw in jd["keywords"] if kw in candidate_text)
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
):
    """Upload a ZIP of PDF/image resumes → extract → rank. Poll /status/{job_id}."""
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a .zip")

    total_w = round(skill_weight + semantic_weight + behavioral_weight, 2)
    if abs(total_w - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail=f"Weights must sum to 1.0, got {total_w}")

    contents = await file.read()
    size_mb  = len(contents) / (1024 * 1024)
    if size_mb > PDF_SIZE_LIMIT_MB:
        raise HTTPException(status_code=400, detail=f"ZIP too large ({size_mb:.1f} MB). Live limit is {PDF_SIZE_LIMIT_MB} MB.")

    job_id      = str(uuid.uuid4())
    job_dir     = TEMP_DIR / job_id
    job_dir.mkdir()
    zip_path    = job_dir / "resumes.zip"
    output_path = job_dir / "submission.csv"

    with open(zip_path, "wb") as f:
        f.write(contents)

    JOBS[job_id] = {"status":"running","step":"Queued...","pct":0,"output":str(output_path),"total_candidates":0,"error":None}

    background_tasks.add_task(
        _run_bulk_pdf,
        job_id, str(zip_path), str(output_path),
        skill_weight, semantic_weight, behavioral_weight, top_n
    )
    return {"job_id": job_id, "status": "running"}


def _upd(job_id, step, pct, status="running"):
    if job_id in JOBS:
        JOBS[job_id].update({"step": step, "pct": pct, "status": status})


def _run_bulk_pdf(job_id, zip_path, output_path, w1, w2, w3, top_n):
    try:
        import zipfile, pandas as pd, numpy as np
        from extractor import extract_from_text, extract_text_from_pdf, extract_text_from_image
        from utils import normalize_0_1
        from feature_engineering import get_features, MUST_HAVE_SKILLS, _get_full_text

        _upd(job_id, "Opening ZIP...", 5)

        SUPPORTED = (".pdf", ".jpg", ".jpeg", ".png", ".webp")
        candidates = []

        with zipfile.ZipFile(zip_path, "r") as z:
            files = [f for f in z.namelist()
                     if any(f.lower().endswith(ext) for ext in SUPPORTED)
                     and not f.startswith("__")]

            if len(files) > PDF_COUNT_LIMIT:
                files = files[:PDF_COUNT_LIMIT]
                _upd(job_id, f"Capped to {PDF_COUNT_LIMIT} files (live server limit)", 6)

            JOBS[job_id]["total_candidates"] = len(files)
            tmp = Path(zip_path).parent / "files"
            tmp.mkdir(exist_ok=True)

            for i, fname in enumerate(files):
                try:
                    data = z.read(fname)
                    fpath = tmp / f"{i}{Path(fname).suffix}"
                    with open(fpath, "wb") as f:
                        f.write(data)
                    if fname.lower().endswith(".pdf"):
                        text = extract_text_from_pdf(str(fpath))
                    else:
                        text = extract_text_from_image(str(fpath))
                    if text.strip():
                        candidates.append(extract_from_text(text, fname))
                except Exception:
                    pass
                _upd(job_id, f"Extracted {i+1}/{len(files)} files...", 5 + int((i/len(files))*45))

        if not candidates:
            raise ValueError("Could not extract text from any file.")

        _upd(job_id, f"Extracted {len(candidates)} resumes. Scoring...", 55)
        feat_df = pd.DataFrame([get_features(c) for c in candidates])

        combined_skill = (feat_df["skill_score"]*0.5 + feat_df["experience_score"]*0.25 +
                          feat_df["title_score"]*0.15 + feat_df["education_score"]*0.10)

        _upd(job_id, "Combining scores...", 80)
        final_scores = (w1 * normalize_0_1(combined_skill.values) +
                        w2 * normalize_0_1(np.array([0.5]*len(candidates))) +
                        w3 * normalize_0_1(feat_df["behavioral_score"].values))

        top_idx = np.argsort(-final_scores)[:top_n]
        rows = []
        for rank, idx in enumerate(top_idx, 1):
            c = candidates[idx]
            p = c.get("profile", {})
            skill_hits = sum(1 for kw in MUST_HAVE_SKILLS if kw in _get_full_text(c).lower())
            rows.append({
                "candidate_id": c["candidate_id"],
                "name":         p.get("name", "Unknown"),
                "rank":         rank,
                "score":        round(float(final_scores[idx]), 4),
                "reasoning":    f"{p.get('current_title','?')} with {p.get('years_of_experience',0):.1f} yrs exp; {skill_hits} JD skill matches.",
                "source_file":  c.get("_source_file", ""),
            })

        pd.DataFrame(rows).to_csv(output_path, index=False)
        _upd(job_id, "Done!", 100, "done")

    except Exception as e:
        JOBS[job_id].update({"status":"error","error":str(e),"step":f"Error: {e}"})
