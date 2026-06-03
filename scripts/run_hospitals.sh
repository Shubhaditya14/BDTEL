#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -x ".venv/bin/python" ]; then
    echo "Missing .venv. Create/activate the virtual environment first."
    exit 1
fi

echo "Running Hospital A, B, and C concurrently"

.venv/bin/python client/hospital_A.py &
PID_A=$!

.venv/bin/python client/hospital_B.py &
PID_B=$!

.venv/bin/python client/hospital_C.py &
PID_C=$!

wait "$PID_A" "$PID_B" "$PID_C"

echo "All hospital clients finished."
