#!/bin/bash

# run this from inside the Hirer/ folder
cd "$(dirname "$0")"

echo "Starting Hirer..."
echo ""

# ── Backend ──────────────────────────────────────────────────
echo "[1/2] Starting FastAPI backend on http://localhost:8000"
cd hirer-backend

if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt -q

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
deactivate
cd ..

sleep 3

# ── Frontend ─────────────────────────────────────────────────
echo "[2/2] Starting Next.js frontend on http://localhost:3000"
cd hirer-frontend

if [ ! -d "node_modules" ]; then
  echo "Installing frontend dependencies..."
  npm install
fi

npx next dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "Both servers running!"
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" EXIT INT TERM
wait
