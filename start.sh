#!/bin/bash

echo "Starting Hirer..."
echo ""

# start backend
echo "[1/2] Starting FastAPI backend on http://localhost:8000"
cd hirer-backend

# create venv if it doesnt exist
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python -m venv venv
fi

# activate and install
source venv/bin/activate
pip install -r requirements.txt -q

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# wait for backend to start
sleep 3

# start frontend
echo "[2/2] Starting Next.js frontend on http://localhost:3000"
cd hirer-frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "Both servers running!"
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; deactivate 2>/dev/null; echo 'Stopped.'" EXIT INT TERM
wait
