#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

kill_port() {
    local port="$1"
    local pids

    pids="$(lsof -ti "tcp:${port}" || true)"

    if [ -n "$pids" ]; then
        echo "Stopping processes on port ${port}: ${pids}"
        kill -TERM $pids || true
        sleep 2

        pids="$(lsof -ti "tcp:${port}" || true)"
        if [ -n "$pids" ]; then
            echo "Force stopping processes on port ${port}: ${pids}"
            kill -9 $pids || true
        fi
    else
        echo "No process found on port ${port}"
    fi
}

echo "Stopping FastAPI, Streamlit, and hospital clients..."
kill_port 8000
kill_port 8501
pkill -f "client/hospital_A.py" 2>/dev/null || true
pkill -f "client/hospital_B.py" 2>/dev/null || true
pkill -f "client/hospital_C.py" 2>/dev/null || true

echo "Clearing local generated storage..."
find server/storage/updates -mindepth 1 ! -name ".DS_Store" -exec rm -rf {} + 2>/dev/null || true
find server/storage/models -mindepth 1 ! -name ".DS_Store" -exec rm -rf {} + 2>/dev/null || true
rm -f server/storage/metrics/metrics.csv
rm -f server/state.json server/state.json.tmp
rm -rf artifacts
rm -f logs/server.log logs/dashboard.log 2>/dev/null || true

if command -v hdfs >/dev/null 2>&1; then
    echo "Clearing HDFS generated storage under /trustfl..."
    hdfs dfs -rm -r -f '/trustfl/updates/*' 2>/dev/null || true
    hdfs dfs -rm -r -f '/trustfl/models/*' 2>/dev/null || true
    hdfs dfs -rm -r -f '/trustfl/metrics/*' 2>/dev/null || true
fi

echo "Reset complete."
