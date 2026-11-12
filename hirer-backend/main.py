"""
Hirer backend: a FastAPI server around the ranking pipeline in hirer_core.

Long work runs in the background and the frontend polls for progress, so no
HTTP response is held open (hosting proxies buffer streamed responses).

  Jobs            GET  /jobs            built-in jobs
                  POST /parse-job       what Hirer reads out of a pasted job description
  Profiles file   POST /rank            -> job_id
  Single resume   POST /extract-single  fields for the form (pre-filled)
                  POST /match-single    the edited candidate matched to the built-in jobs
  Resume ZIP      POST /extract-bulk    -> job_id, then GET /extracted/{id}
                  POST /rank-bulk       recruiter's edits + job + weights -> job_id
  Any job_id      GET  /status/{id}  /preview/{id}  /download/{id}

Settings (environment variables, all optional; 0 or empty means off):
  FRONTEND_URL             extra allowed origins, comma-separated
  JSONL_ENTRY_LIMIT        max profiles per file
  PDF_COUNT_LIMIT          max resumes per ZIP
  PDF_SIZE_LIMIT_MB        max ZIP size
  RATE_LIMIT_PER_MIN       max uploads per minute from one address
  HIRER_ACCESS_CODE        code required for the recruiter tools
  HIRER_DATA_DIR           where job records and results are kept
  HIRER_RETENTION_MINUTES  how long results are kept (default 60)
  HIRER_VERIFY_GITHUB      1 = look up GitHub accounts named on resumes
"""

import copy
import csv
import hmac
import json
import os
import shutil
import sys
import tempfile
import time
import uuid
import zipfile
from collections import defaultdict, deque
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# this folder (extractor, resumes, store) and the repo root (the shared hirer_core package)
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))

from hirer_core import PRESETS, get_job, rank                # noqa: E402
from hirer_core import semantic                              # noqa: E402
from hirer_core.utils import load_candidates                 # noqa: E402
from extractor import extract_from_text, extract_text_from_image, extract_text_from_pdf   # noqa: E402
from resumes import RESUME_EXTS, apply_edits, find_detail_files, github_summary, match_jobs, summary  # noqa: E402
from store import JobStore                                   # noqa: E402

JSONL_ENTRY_LIMIT = int(os.environ.get("JSONL_ENTRY_LIMIT", "0"))
PDF_COUNT_LIMIT = int(os.environ.get("PDF_COUNT_LIMIT", "0"))
PDF_SIZE_LIMIT_MB = float(os.environ.get("PDF_SIZE_LIMIT_MB", "0"))
RATE_LIMIT_PER_MIN = int(os.environ.get("RATE_LIMIT_PER_MIN", "0"))
ACCESS_CODE = os.environ.get("HIRER_ACCESS_CODE", "")
RETENTION_SECONDS = int(os.environ.get("HIRER_RETENTION_MINUTES", "60")) * 60
DATA_DIR = Path(os.environ.get("HIRER_DATA_DIR") or Path(tempfile.gettempdir()) / "hirer")
DATA_DIR.mkdir(parents=True, exist_ok=True)

JOBS = JobStore(DATA_DIR / "jobs.sqlite3")
RANK_COLUMNS = ["candidate_id", "rank", "score", "reasoning"]
RESUME_COLUMNS = ["candidate_id", "name", "rank", "score", "reasoning", "source_file"]

app = FastAPI(title="Hirer API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"]
                  + [o.strip() for o in os.environ.get("FRONTEND_URL", "").split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── guards ────────────────────────────────────────────────────────────────────

_hits = defaultdict(deque)


def rate_limit(request: Request):
    """at most RATE_LIMIT_PER_MIN uploads a minute from one address"""
    if not RATE_LIMIT_PER_MIN:
        return
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    now = time.time()
    recent = _hits[ip]
    while recent and recent[0] < now - 60:
        recent.popleft()
    if len(recent) >= RATE_LIMIT_PER_MIN:
        raise HTTPException(status_code=429, detail="Too many requests from your address. Try again in a minute.")
    recent.append(now)


def recruiter(x_access_code: str | None = Header(None)):
    """the recruiter tools need the access code when the server has one set"""
    if ACCESS_CODE and not hmac.compare_digest((x_access_code or "").encode(), ACCESS_CODE.encode()):
        raise HTTPException(status_code=401, detail="This server needs an access code for the recruiter tools.")


_last_cleanup = 0.0


def cleanup():
    """delete results older than the retention period (checked at most every 5 minutes)"""
    global _last_cleanup
    if time.time() - _last_cleanup < 300:
        return
    _last_cleanup = time.time()
    for job_id in JOBS.purge(RETENTION_SECONDS):
        shutil.rmtree(DATA_DIR / job_id, ignore_errors=True)
    for ip in [ip for ip, q in _hits.items() if not q]:
        del _hits[ip]


def new_job(kind, **fields):
    cleanup()
    job_id = str(uuid.uuid4())
    (DATA_DIR / job_id).mkdir()
    JOBS.create(job_id, kind=kind, **fields)
    return job_id, DATA_DIR / job_id


def finished_job(job_id, kind=None):
    job = JOBS.get(job_id)
    if not job or (kind and job.get("kind") != kind) or job["status"] != "done":
        raise HTTPException(status_code=404, detail="Not found, not finished yet, or already deleted. Run it again.")
    return job


def check_weights(*weights):
    total = round(sum(weights), 2)
    if abs(total - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail=f"Weights must sum to 1.0, got {total}")


def pick_job(preset, text, extra_skills, use_semantic, use_rerank):
    try:
        job = get_job(preset=preset, text=text, extra_skills=(extra_skills or "").split(","))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if (use_semantic or use_rerank) and not semantic.available():
        raise HTTPException(status_code=400, detail="Semantic matching isn't installed on this server "
                                                    "(pip install sentence-transformers).")
    if not job.must_have and not use_semantic:
        raise HTTPException(status_code=400, detail="No known skills were found in the job description. "
                                                    "Add must-have skills, or turn on semantic matching.")
    return job


# ── general ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/config")
def config():
    """what this server allows, so the frontend can show the right limits and options"""
    return {
        "jsonl_limit": JSONL_ENTRY_LIMIT,
        "pdf_limit": PDF_COUNT_LIMIT,
        "size_limit_mb": PDF_SIZE_LIMIT_MB,
        "access_required": bool(ACCESS_CODE),
        "semantic_available": semantic.available(),
        "embed_model": semantic.EMBED_MODEL,
        "retention_minutes": RETENTION_SECONDS // 60,
    }


@app.get("/jobs")
def jobs():
    return {"jobs": [j.to_dict() for j in PRESETS]}


class ParseJobRequest(BaseModel):
    text: str
    extra_skills: str = ""


@app.post("/parse-job")
def parse_job_text(req: ParseJobRequest):
    """what Hirer understood from a pasted job description"""
    if len(req.text) > 20000:
        raise HTTPException(status_code=400, detail="Job description is too long (20,000 characters max).")
    if not req.text.strip():
        return {"title": "", "must_have": [], "nice_to_have": [], "negative": [], "years": None, "locations": []}
    return get_job(text=req.text, extra_skills=req.extra_skills.split(",")).to_dict()


@app.get("/status/{job_id}")
def get_status(job_id: str):
    """Poll this for progress. status is 'running' | 'done' | 'error'."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **{k: job[k] for k in ("status", "step", "pct", "steps", "error", "result")}}


@app.get("/preview/{job_id}")
def preview_result(job_id: str, limit: int = 20):
    """the top rows of a finished ranking, with score breakdowns"""
    job = finished_job(job_id, "rank")
    with open(DATA_DIR / job_id / "rows.json") as f:
        rows = json.load(f)
    return {"results": rows[:limit], "meta": job["result"]}


@app.get("/download/{job_id}")
def download_result(job_id: str):
    finished_job(job_id, "rank")
    path = DATA_DIR / job_id / "ranked.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Output file not found")
    return FileResponse(path, media_type="text/csv", filename="hirer_ranked.csv")


def _finish(job_id, result, columns):
    """write the CSV and the full rows, mark the job done"""
    rows = result["rows"]
    job_dir = DATA_DIR / job_id
    with open(job_dir / "ranked.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    with open(job_dir / "rows.json", "w") as f:
        json.dump(rows, f)
    meta = {k: result[k] for k in ("total_candidates", "weights_used", "reference_date", "relative",
                                   "reranked", "job")}
    meta.update(job_id=job_id, ranked=len(rows), job_title=result["job"]["title"],
                top_candidate=rows[0]["candidate_id"] if rows else None,
                top_score=rows[0]["score"] if rows else None)
    JOBS.update(job_id, status="done", pct=100, step="Done!", add_step="Done!", result=meta)


def _run_rank(job_id, candidates, job, weights, top_n, use_semantic, use_rerank, columns):
    try:
        result = rank(candidates, weights, use_semantic=use_semantic, top_n=top_n, job=job,
                      use_rerank=use_rerank, progress=lambda step, pct: JOBS.step(job_id, step, pct))
        _finish(job_id, result, columns)
    except Exception as e:
        JOBS.update(job_id, status="error", error=str(e), step=f"Error: {e}")


# ── profiles file ─────────────────────────────────────────────────────────────

@app.post("/rank", dependencies=[Depends(rate_limit), Depends(recruiter)])
async def rank_candidates(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    skill_weight: float = Form(0.40),
    semantic_weight: float = Form(0.35),
    behavioral_weight: float = Form(0.25),
    top_n: int = Form(100),
    use_semantic: bool = Form(False),
    use_rerank: bool = Form(False),
    job_preset: int | None = Form(None),
    job_text: str = Form(""),
    extra_skills: str = Form(""),
):
    """Upload a candidates.jsonl file and rank it in the background. Poll /status/{job_id}."""
    check_weights(skill_weight, semantic_weight, behavioral_weight)
    if not (file.filename or "").endswith((".jsonl", ".json")):
        raise HTTPException(status_code=400, detail="File must be .jsonl or .json")
    job = pick_job(job_preset, job_text, extra_skills, use_semantic, use_rerank)

    if JSONL_ENTRY_LIMIT:
        n_entries = sum(1 for line in file.file if line.strip())
        file.file.seek(0)
        if n_entries > JSONL_ENTRY_LIMIT:
            raise HTTPException(
                status_code=400,
                detail=f"This server accepts up to {JSONL_ENTRY_LIMIT:,} entries per file; yours has "
                       f"{n_entries:,}. Run Hirer locally for larger files.")

    job_id, job_dir = new_job("rank")
    input_path = job_dir / "candidates.jsonl"
    with open(input_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    weights = {"skill": skill_weight, "semantic": semantic_weight, "behavioral": behavioral_weight}

    def run():
        try:
            JOBS.step(job_id, "Loading candidates...", 10)
            candidates = load_candidates(str(input_path))
            JOBS.step(job_id, f"Loaded {len(candidates):,} candidates", 20)
        except Exception as e:
            JOBS.update(job_id, status="error", error=f"Could not read the file: {e}", step="Error")
            return
        finally:
            input_path.unlink(missing_ok=True)      # the upload isn't needed once it is in memory
        _run_rank(job_id, candidates, job, weights, top_n, use_semantic, use_rerank, RANK_COLUMNS)

    background_tasks.add_task(run)
    return {"job_id": job_id, "status": "running"}


# ── single resume ─────────────────────────────────────────────────────────────

def _read_resume(path: Path):
    if path.suffix.lower() == ".pdf":
        return extract_text_from_pdf(str(path))
    return extract_text_from_image(str(path))


def _candidate_from(path: Path, name: str):
    """a structured candidate from a resume file, or None if no text could be read"""
    text = _read_resume(path)
    if not text.strip():
        return None
    candidate = extract_from_text(text, name)
    gh = github_summary(candidate["profile"].get("github"))
    if gh:
        candidate["_github"] = gh
    return candidate


@app.post("/extract-single", dependencies=[Depends(rate_limit)])
async def extract_single(file: UploadFile = File(...)):
    """Read one PDF/image resume and return its fields for the form."""
    fname = Path(file.filename or "resume").name
    if not fname.lower().endswith(RESUME_EXTS):
        raise HTTPException(status_code=400, detail="File must be a PDF or image (JPG/PNG)")

    with tempfile.TemporaryDirectory() as tmp:      # the resume is deleted as soon as it is read
        path = Path(tmp) / fname
        path.write_bytes(await file.read())
        candidate = _candidate_from(path, fname)

    if candidate is None:
        raise HTTPException(
            status_code=422,
            detail="Could not read any text from this file. If it is a scan or photo, try a clearer image "
                   "or a text-based PDF (one where you can select the text).")
    return {"candidate": candidate, "fields": summary(candidate)}


class MatchSingleRequest(BaseModel):
    candidate: dict
    edits: dict = {}


@app.post("/match-single")
def match_single(req: MatchSingleRequest):
    """Match the candidate, with the person's own corrections and additions, to the built-in jobs."""
    candidate = apply_edits(req.candidate, req.edits)
    results = match_jobs(candidate)
    p = candidate.get("profile", {})
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
            "github":              candidate.get("_github"),
        },
        "job_matches": results,
        "best_match":  results[0]["job_title"] if results else None,
        "top_domain":  results[0]["domain"] if results else None,
    }


# ── resume ZIP ────────────────────────────────────────────────────────────────

@app.post("/extract-bulk", dependencies=[Depends(rate_limit), Depends(recruiter)])
async def extract_bulk(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload a ZIP of resumes (plus optional detail files). Poll /status/{job_id}."""
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a .zip")
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if PDF_SIZE_LIMIT_MB and size_mb > PDF_SIZE_LIMIT_MB:
        raise HTTPException(status_code=400,
                            detail=f"ZIP too large ({size_mb:.1f} MB). Live limit is {PDF_SIZE_LIMIT_MB} MB.")

    job_id, job_dir = new_job("extract")
    (job_dir / "resumes.zip").write_bytes(contents)
    background_tasks.add_task(_run_extract_bulk, job_id)
    return {"job_id": job_id, "status": "running"}


def _run_extract_bulk(job_id):
    job_dir = DATA_DIR / job_id
    zip_path, tmp = job_dir / "resumes.zip", job_dir / "files"
    try:
        JOBS.step(job_id, "Opening ZIP...", 5)
        candidates, skipped = [], []

        with zipfile.ZipFile(zip_path, "r") as z:
            files = sorted(f for f in z.namelist()
                           if f.lower().endswith(RESUME_EXTS) and not f.startswith("__")
                           and "/." not in f and not f.startswith("."))
            if not files:
                raise ValueError("No PDF or image resumes found in the ZIP.")
            if PDF_COUNT_LIMIT and len(files) > PDF_COUNT_LIMIT:
                files = files[:PDF_COUNT_LIMIT]
                JOBS.step(job_id, f"Capped to {PDF_COUNT_LIMIT} files (live server limit)", 6)

            details = find_detail_files(z, files)
            if details:
                JOBS.step(job_id, f"Found detail files for {len(details)} of {len(files)} resumes", 8)

            tmp.mkdir(exist_ok=True)
            for i, fname in enumerate(files):
                short = Path(fname).name
                try:
                    fpath = tmp / f"{i}{Path(fname).suffix.lower()}"
                    fpath.write_bytes(z.read(fname))
                    c = _candidate_from(fpath, short)
                    if c is None:
                        skipped.append(short)
                    else:
                        if fname in details:
                            raw, source = details[fname]
                            apply_edits(c, raw)
                            c["_details_source"] = source
                        candidates.append(c)
                except Exception:
                    skipped.append(short)
                JOBS.step(job_id, f"Read {i + 1}/{len(files)}: {short}", 10 + int((i + 1) / len(files) * 85))

        if not candidates:
            raise ValueError("Could not read text from any resume in the ZIP.")

        with open(job_dir / "candidates.json", "w") as f:
            json.dump({"candidates": candidates, "skipped": skipped}, f)
        JOBS.update(job_id, status="done", pct=100, step="Done!", add_step="Done!", result={
            "job_id": job_id, "total_candidates": len(candidates),
            "with_details": sum(1 for c in candidates if summary(c)["has_details"]), "skipped": skipped})

    except Exception as e:
        JOBS.update(job_id, status="error", error=str(e), step=f"Error: {e}")
    finally:
        # the original files are deleted once they have been read
        zip_path.unlink(missing_ok=True)
        shutil.rmtree(tmp, ignore_errors=True)


def _extracted(job_id):
    finished_job(job_id, "extract")
    with open(DATA_DIR / job_id / "candidates.json") as f:
        return json.load(f)


@app.get("/extracted/{job_id}")
def get_extracted(job_id: str):
    """Every resume from the ZIP, with its extracted fields and whether details were supplied."""
    data = _extracted(job_id)
    return {"resumes": [summary(c) for c in data["candidates"]], "skipped": data["skipped"]}


class RankBulkRequest(BaseModel):
    extract_job_id: str
    edits: dict[str, dict] = {}
    skill_weight: float = 0.40
    semantic_weight: float = 0.35
    behavioral_weight: float = 0.25
    top_n: int = 50
    use_semantic: bool = False
    use_rerank: bool = False
    job_preset: int | None = None
    job_text: str = ""
    extra_skills: str = ""


@app.post("/rank-bulk", dependencies=[Depends(rate_limit), Depends(recruiter)])
def rank_bulk(req: RankBulkRequest, background_tasks: BackgroundTasks):
    """Rank the extracted resumes after the recruiter's edits. Poll /status/{job_id}."""
    check_weights(req.skill_weight, req.semantic_weight, req.behavioral_weight)
    job = pick_job(req.job_preset, req.job_text, req.extra_skills, req.use_semantic, req.use_rerank)
    candidates = copy.deepcopy(_extracted(req.extract_job_id)["candidates"])
    for c in candidates:
        if req.edits.get(c["candidate_id"]):
            apply_edits(c, req.edits[c["candidate_id"]])

    job_id, _ = new_job("rank")
    JOBS.step(job_id, f"Scoring {len(candidates)} resumes...", 20)
    weights = {"skill": req.skill_weight, "semantic": req.semantic_weight, "behavioral": req.behavioral_weight}
    background_tasks.add_task(_run_rank, job_id, candidates, job, weights, req.top_n,
                              req.use_semantic, req.use_rerank, RESUME_COLUMNS)
    return {"job_id": job_id, "status": "running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
