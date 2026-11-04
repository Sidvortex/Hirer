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
        "relative": result["relative"],
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


# ── Resume modes ──────────────────────────────────────────────────────────────
#
# Single resume:  POST /extract-single  -> fields for the form (pre-filled)
#                 POST /match-single    -> the edited candidate, matched to jobs
# Bulk ZIP:       POST /extract-bulk    -> job; poll /status, then GET /extracted/{id}
#                                          lists every resume and whether a detail
#                                          file already supplied its info
#                 POST /rank-bulk       -> recruiter's edits + weights; poll /status,
#                                          then /preview and /download as usual

from pydantic import BaseModel  # noqa: E402
from resumes import (  # noqa: E402
    RESUME_EXTS, apply_edits, summary, find_detail_files, match_jobs,
)


def _read_resume(path: Path):
    from extractor import extract_text_from_pdf, extract_text_from_image
    if path.suffix.lower() == ".pdf":
        return extract_text_from_pdf(str(path))
    return extract_text_from_image(str(path))


@app.post("/extract-single")
async def extract_single(file: UploadFile = File(...)):
    """Read one PDF/image resume and return its fields for the form."""
    from extractor import extract_from_text

    fname = file.filename or "resume"
    if not fname.lower().endswith(RESUME_EXTS):
        raise HTTPException(status_code=400, detail="File must be a PDF or image (JPG/PNG)")

    job_dir = TEMP_DIR / str(uuid.uuid4())
    job_dir.mkdir()
    path = job_dir / Path(fname).name
    path.write_bytes(await file.read())
    try:
        text = _read_resume(path)
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)

    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail="Could not read any text from this file. If it is a scan or photo, try a clearer image "
                   "or a text-based PDF (one where you can select the text).",
        )

    candidate = extract_from_text(text, fname)
    return {"candidate": candidate, "fields": summary(candidate)}


class MatchSingleRequest(BaseModel):
    candidate: dict
    edits: dict = {}


@app.post("/match-single")
def match_single(req: MatchSingleRequest):
    """Match the candidate, with the person's own corrections and additions, to the job list."""
    candidate = apply_edits(req.candidate, req.edits)
    results = match_jobs(candidate)
    p = candidate["profile"]
    d = candidate.get("_details") or {}
    return {
        "candidate": {
            "name":                p.get("name", ""),
            "current_title":       p.get("current_title", ""),
            "years_of_experience": p.get("years_of_experience", 0),
            "skills_found":        [s["name"] for s in candidate.get("skills", [])][:12],
            "location":            p.get("location", ""),
            "industry":            p.get("current_industry", ""),
            "notice_period_days":  d.get("notice_period_days"),
            "willing_to_relocate": d.get("willing_to_relocate"),
            "expected_role":       d.get("expected_role", ""),
        },
        "job_matches": results,
        "best_match":  results[0]["job_title"] if results else None,
        "top_domain":  results[0]["domain"] if results else None,
    }


@app.post("/screen-single")
async def screen_single_resume(file: UploadFile = File(...)):
    """One step, no form: extract and match straight away."""
    extracted = await extract_single(file)
    return match_single(MatchSingleRequest(candidate=extracted["candidate"]))


@app.post("/extract-bulk")
async def extract_bulk(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload a ZIP of resumes (plus optional detail files). Poll /status/{job_id}."""
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a .zip")

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if PDF_SIZE_LIMIT_MB and size_mb > PDF_SIZE_LIMIT_MB:
        raise HTTPException(status_code=400, detail=f"ZIP too large ({size_mb:.1f} MB). Live limit is {PDF_SIZE_LIMIT_MB} MB.")

    job_id = str(uuid.uuid4())
    job_dir = TEMP_DIR / job_id
    job_dir.mkdir()
    zip_path = job_dir / "resumes.zip"
    zip_path.write_bytes(contents)

    JOBS[job_id] = {"status": "running", "step": "Queued...", "pct": 0, "steps": [],
                    "kind": "extract", "candidates": [], "skipped": [], "error": None, "result": None}
    background_tasks.add_task(_run_extract_bulk, job_id, str(zip_path))
    return {"job_id": job_id, "status": "running"}


def _upd(job_id, step, pct, status="running"):
    if job_id in JOBS:
        JOBS[job_id].update({"step": step, "pct": pct, "status": status})
        JOBS[job_id]["steps"].append(step)


def _run_extract_bulk(job_id, zip_path):
    try:
        import zipfile
        from extractor import extract_from_text

        _upd(job_id, "Opening ZIP...", 5)
        candidates, skipped = [], []

        with zipfile.ZipFile(zip_path, "r") as z:
            files = sorted(f for f in z.namelist()
                           if f.lower().endswith(RESUME_EXTS) and not f.startswith("__")
                           and "/." not in f and not f.startswith("."))
            if not files:
                raise ValueError("No PDF or image resumes found in the ZIP.")
            if PDF_COUNT_LIMIT and len(files) > PDF_COUNT_LIMIT:
                files = files[:PDF_COUNT_LIMIT]
                _upd(job_id, f"Capped to {PDF_COUNT_LIMIT} files (live server limit)", 6)

            details = find_detail_files(z, files)
            if details:
                _upd(job_id, f"Found detail files for {len(details)} of {len(files)} resumes", 8)

            tmp = Path(zip_path).parent / "files"
            tmp.mkdir(exist_ok=True)
            for i, fname in enumerate(files):
                short = Path(fname).name
                try:
                    fpath = tmp / f"{i}{Path(fname).suffix.lower()}"
                    fpath.write_bytes(z.read(fname))
                    text = _read_resume(fpath)
                    if text.strip():
                        c = extract_from_text(text, short)
                        if fname in details:
                            raw, source = details[fname]
                            apply_edits(c, raw)
                            c["_details_source"] = source
                        candidates.append(c)
                    else:
                        skipped.append(short)
                except Exception:
                    skipped.append(short)
                _upd(job_id, f"Read {i + 1}/{len(files)}: {short}", 10 + int((i + 1) / len(files) * 85))

        if not candidates:
            raise ValueError("Could not read text from any resume in the ZIP.")

        JOBS[job_id]["candidates"] = candidates
        JOBS[job_id]["skipped"] = skipped
        JOBS[job_id]["result"] = {"job_id": job_id, "total_candidates": len(candidates),
                                  "with_details": sum(1 for c in candidates if summary(c)["has_details"]),
                                  "skipped": skipped}
        _upd(job_id, "Done!", 100, "done")

    except Exception as e:
        JOBS[job_id].update({"status": "error", "error": str(e), "step": f"Error: {e}"})


@app.get("/extracted/{job_id}")
def get_extracted(job_id: str):
    """Every resume from the ZIP, with its extracted fields and whether details were supplied."""
    job = JOBS.get(job_id)
    if not job or job.get("kind") != "extract" or job["status"] != "done":
        raise HTTPException(status_code=404, detail="Extraction not found or not complete")
    return {"resumes": [summary(c) for c in job["candidates"]], "skipped": job["skipped"]}


class RankBulkRequest(BaseModel):
    extract_job_id: str
    edits: dict[str, dict] = {}
    skill_weight: float = 0.40
    semantic_weight: float = 0.35
    behavioral_weight: float = 0.25
    top_n: int = 50
    use_semantic: bool = False


@app.post("/rank-bulk")
def rank_bulk(req: RankBulkRequest, background_tasks: BackgroundTasks):
    """Rank the extracted resumes after the recruiter's edits. Poll /status/{job_id}."""
    import copy

    src = JOBS.get(req.extract_job_id)
    if not src or src.get("kind") != "extract" or src["status"] != "done":
        raise HTTPException(status_code=404, detail="Extraction not found. Upload the ZIP again.")
    total = round(req.skill_weight + req.semantic_weight + req.behavioral_weight, 2)
    if abs(total - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail=f"Weights must sum to 1.0, got {total}")

    candidates = copy.deepcopy(src["candidates"])
    for c in candidates:
        e = req.edits.get(c["candidate_id"])
        if e:
            apply_edits(c, e)

    job_id = str(uuid.uuid4())
    job_dir = TEMP_DIR / job_id
    job_dir.mkdir()
    output_path = job_dir / "submission.csv"
    JOBS[job_id] = {"status": "running", "step": "Queued...", "pct": 0, "steps": [],
                    "output": str(output_path), "error": None, "result": None}
    background_tasks.add_task(_run_rank_bulk, job_id, candidates, str(output_path), req)
    return {"job_id": job_id, "status": "running"}


def _run_rank_bulk(job_id, candidates, output_path, req):
    try:
        _upd(job_id, f"Scoring {len(candidates)} resumes...", 20)
        result = rank(
            candidates,
            {"skill": req.skill_weight, "semantic": req.semantic_weight, "behavioral": req.behavioral_weight},
            use_semantic=req.use_semantic,
            top_n=req.top_n,
            progress=lambda step, pct: _upd(job_id, step, pct),
        )
        _finish(job_id, result, output_path, ["candidate_id", "name", "rank", "score", "reasoning", "source_file"])
    except Exception as e:
        JOBS[job_id].update({"status": "error", "error": str(e), "step": f"Error: {e}"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
