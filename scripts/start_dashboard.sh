#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -x ".venv/bin/streamlit" ]; then
    echo "Missing Streamlit in .venv."
    exit 1
fi

echo "Starting Streamlit dashboard on http://127.0.0.1:8501"
exec .venv/bin/streamlit run dashboard/app.py
