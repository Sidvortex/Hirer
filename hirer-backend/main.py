"""
Hirer Backend — FastAPI server wrapping the ranking pipeline
"""

import os
import sys
import json
import uuid
import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

# add current dir to path so ranking.py imports work
sys.path.insert(0, os.path.dirname(__file__))

app = FastAPI(title="Hirer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
    file: UploadFile = File(...),
    skill_weight: float = Form(0.40),
    semantic_weight: float = Form(0.35),
    behavioral_weight: float = Form(0.25),
    top_n: int = Form(100),
    use_semantic: bool = Form(False),
):
    """
    Upload a candidates.jsonl file and get back a ranked CSV.
    Streams progress as Server-Sent Events.
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
        "input": str(input_path),
        "output": str(output_path),
        "weights": (skill_weight, semantic_weight, behavioral_weight),
        "top_n": top_n,
        "use_semantic": use_semantic,
    }

    async def run_and_stream() -> AsyncGenerator[str, None]:
        try:
            yield _sse("start", {"job_id": job_id, "message": "Pipeline started"})

            # load candidates
            yield _sse("progress", {"step": "Loading candidates...", "pct": 10})
            await asyncio.sleep(0.1)

            from utils import load_candidates, normalize_0_1, build_candidate_text
            from feature_engineering import get_features, MUST_HAVE_SKILLS, _get_full_text

            candidates = load_candidates(str(input_path))
            yield _sse("progress", {"step": f"Loaded {len(candidates):,} candidates", "pct": 20})
            await asyncio.sleep(0.1)

            # feature scores
            yield _sse("progress", {"step": "Computing keyword scores...", "pct": 30})
            import numpy as np
            import pandas as pd

            feature_rows = []
            for c in candidates:
                feature_rows.append(get_features(c))

            feat_df = pd.DataFrame(feature_rows)
            combined_skill = (
                feat_df["skill_score"] * 0.5 +
                feat_df["experience_score"] * 0.25 +
                feat_df["title_score"] * 0.15 +
                feat_df["education_score"] * 0.10
            )

            yield _sse("progress", {"step": "Keyword scores done", "pct": 45})
            await asyncio.sleep(0.1)

            # semantic scores
            if use_semantic:
                yield _sse("progress", {"step": "Loading sentence-transformer model...", "pct": 50})
                await asyncio.sleep(0.1)

                from sentence_transformers import SentenceTransformer
                from sklearn.metrics.pairwise import cosine_similarity

                JD_TEXT = """Senior AI Engineer at Redrob AI. Requirements: embeddings, sentence-transformers,
                vector databases, FAISS, Pinecone, Qdrant, Python, NDCG, MRR, semantic search, NLP, LLM fine-tuning.
                5-9 years experience. Pune or Noida India."""

                model = SentenceTransformer("all-MiniLM-L6-v2")
                jd_emb = model.encode([JD_TEXT])

                yield _sse("progress", {"step": "Encoding candidates...", "pct": 60})
                texts = [build_candidate_text(c) for c in candidates]

                all_embs = []
                batch_size = 64
                for i in range(0, len(texts), batch_size):
                    batch = texts[i:i+batch_size]
                    emb = model.encode(batch, show_progress_bar=False)
                    all_embs.append(emb)
                    pct = 60 + int((i / len(texts)) * 20)
                    yield _sse("progress", {"step": f"Encoding... {i}/{len(texts)}", "pct": pct})
                    await asyncio.sleep(0)

                all_embs_np = np.vstack(all_embs)
                semantic_scores = cosine_similarity(jd_emb, all_embs_np)[0].tolist()
            else:
                semantic_scores = [0.5] * len(candidates)

            yield _sse("progress", {"step": "Computing behavioral signals...", "pct": 78})
            await asyncio.sleep(0.1)

            behavioral_arr = feat_df["behavioral_score"].values
            semantic_arr = np.array(semantic_scores)

            # combine
            yield _sse("progress", {"step": "Combining weighted scores...", "pct": 85})
            final_scores = (
                skill_weight * normalize_0_1(combined_skill.values) +
                semantic_weight * normalize_0_1(semantic_arr) +
                behavioral_weight * normalize_0_1(behavioral_arr)
            )

            sorted_idx = np.argsort(-final_scores)
            top_idx = sorted_idx[:top_n]

            yield _sse("progress", {"step": f"Ranking top {top_n} candidates...", "pct": 92})
            await asyncio.sleep(0.1)

            # build output
            rows = []
            for rank, idx in enumerate(top_idx, start=1):
                c = candidates[idx]
                text = _get_full_text(c).lower()
                skill_hits = sum(1 for kw in MUST_HAVE_SKILLS if kw in text)
                sig = c.get("redrob_signals", {})
                p = c.get("profile", {})

                parts = [f"{p.get('current_title','?')} with {p.get('years_of_experience',0):.1f} yrs exp"]
                parts.append(f"{skill_hits} JD skill matches")
                if sig.get("open_to_work_flag"): parts.append("open to work")
                if sig.get("github_activity_score", -1) > 50: parts.append(f"GitHub {sig['github_activity_score']:.0f}")
                if sig.get("recruiter_response_rate", 0) > 0.7: parts.append(f"RR {sig['recruiter_response_rate']:.2f}")

                rows.append({
                    "candidate_id": c["candidate_id"],
                    "rank": rank,
                    "score": round(float(final_scores[idx]), 4),
                    "reasoning": "; ".join(parts) + ".",
                })

            out_df = pd.DataFrame(rows)
            out_df.to_csv(str(output_path), index=False)

            JOBS[job_id]["status"] = "done"

            yield _sse("done", {
                "job_id": job_id,
                "total_candidates": len(candidates),
                "ranked": len(rows),
                "top_candidate": rows[0]["candidate_id"] if rows else None,
                "top_score": rows[0]["score"] if rows else None,
            })

        except Exception as e:
            JOBS[job_id]["status"] = "error"
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(
        run_and_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
