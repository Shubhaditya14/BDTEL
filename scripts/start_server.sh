#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -x ".venv/bin/python" ]; then
    echo "Missing .venv. Create/activate the virtual environment first."
    exit 1
fi

mkdir -p logs

echo "Starting FastAPI server on http://127.0.0.1:8000"
exec .venv/bin/python -m uvicorn server.server:app --host 0.0.0.0 --port 8000
