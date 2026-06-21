# Hirer — Full Stack Setup

## Structure

```
hirer-frontend/    ← Next.js app (port 3000)
hirer-backend/     ← FastAPI server (port 8000)
start.sh           ← start both with one command
```

## Quick Start

### Option 1 — One command (recommended)

```bash
chmod +x start.sh
./start.sh
```

This automatically creates a Python venv, installs deps, and starts both servers.

### Option 2 — Manually

**Terminal 1 — Backend:**
```bash
cd hirer-backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd hirer-frontend
npm install
npm run dev
```

Open http://localhost:3000

## Note for Arch Linux users

Do NOT use `pip install` without a venv on Arch.
The start.sh script handles this automatically.

## How it works

1. Boot screen — handwritten Hirer animation, press any key
2. Home screen — floating paths background, click Start Ranking
3. Select screen — radial orbital job selector, upload candidates.jsonl, configure weights
4. Pipeline runs — FastAPI streams live progress to frontend
5. Results screen — top 3 display cards + full table + radial selector to rerank for different jobs
6. About page — team info, accessible from home and results
7. Error page — auto-triggers if backend fails or file is invalid

## API

- POST /rank — upload file + weights, returns SSE progress stream
- GET /download/{job_id} — download ranked CSV
- GET /preview/{job_id}?limit=N — preview results as JSON
- GET /health — check backend status
- Docs at http://localhost:8000/docs
