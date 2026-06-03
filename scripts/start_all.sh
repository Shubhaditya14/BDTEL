#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p logs

echo "Starting FastAPI server..."
.venv/bin/python -m uvicorn server.server:app --host 0.0.0.0 --port 8000 \
    > logs/server.log 2>&1 &
SERVER_PID=$!

echo "FastAPI PID: $SERVER_PID"
sleep 3

echo "Starting Streamlit dashboard..."
.venv/bin/streamlit run dashboard/app.py \
    > logs/dashboard.log 2>&1 &
DASHBOARD_PID=$!

echo "Dashboard PID: $DASHBOARD_PID"
echo "Server:    http://127.0.0.1:8000"
echo "Dashboard: http://127.0.0.1:8501"
echo
echo "To run training clients concurrently:"
echo "  ./scripts/run_hospitals.sh"
