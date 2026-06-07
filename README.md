# BDTEL MVP: Trust-Aware Federated Learning Platform

A full-stack federated learning prototype that simulates privacy-preserving collaboration between hospitals. Each hospital trains locally on its own patient data, uploads only model parameters to a FastAPI server, and the server builds a trust-weighted global model while persisting updates, metrics, and model artifacts locally and in HDFS.

This project was built as a practical ML systems demo: it connects distributed training mechanics, backend APIs, audit storage, Hadoop/HDFS integration, and a live Streamlit dashboard.

## Why This Project Matters

Healthcare ML is often blocked by data privacy constraints. Hospitals may not be able to share raw patient records, but they can still collaborate by sharing model updates. This project demonstrates that workflow end to end:

- Hospitals keep local patient data private.
- A central server receives model weights, not raw records.
- Trust scores reduce the impact of unstable or malicious clients.
- HDFS stores every update and global model as an audit trail.
- A dashboard visualizes training progress, trust ranking, and system status.

## Core Features

- Simulated federated learning with three independent hospital clients.
- Trust-aware aggregation using accuracy and consistency history.
- Malicious hospital simulation for robustness demonstration.
- FastAPI backend with endpoints for uploads, aggregation, metrics, trust, HDFS status, and dashboard data.
- Streamlit dashboard with live metrics, trust ranking, hospital comparison charts, global accuracy, HDFS artifact counts, recent updates, and model repository view.
- HDFS integration for distributed storage of hospital updates, global models, and metrics CSV.
- Scripted demo flow for starting, stopping, resetting, and running all clients concurrently.

## Tech Stack

- Python
- FastAPI
- Uvicorn
- Streamlit
- scikit-learn
- NumPy
- pandas
- Hadoop HDFS
- Bash scripting

## Architecture

```text
Hospital A       Hospital B       Hospital C
local data       local data       local data
    |                |                |
    v                v                v
local model      local model      local model
    |                |                |
    +-------- model weights + metrics --------+
                                             |
                                             v
                                  FastAPI Aggregation Server
                                  - stores updates
                                  - calculates trust
                                  - aggregates global model
                                  - logs metrics
                                             |
                    +------------------------+------------------------+
                    |                        |                        |
                    v                        v                        v
             Local Storage                 HDFS                 Streamlit Dashboard
             JSON + CSV             distributed audit log       live visualization
```

## Project Structure

```text
client/
  dataset.csv
  hospital_A.py
  hospital_B.py
  hospital_C.py

server/
  server.py
  trust.py
  hdfs_storage.py
  state.json
  storage/
    updates/
    metrics/
    models/

dashboard/
  app.py

artifacts/
  round_1/
    Hospital_A.json
    Hospital_B.json
    Hospital_C.json
    global_model.json

scripts/
  start_all.sh
  start_server.sh
  start_dashboard.sh
  run_hospitals.sh
  stop_reset.sh
```

## How The Simulation Works

Each hospital owns a different slice of the dataset:

```text
Hospital_A: patients 0-199
Hospital_B: patients 200-399
Hospital_C: patients 400+
```

For each round:

1. Every hospital trains a local logistic regression model.
2. The hospital uploads accuracy and model weights to the server.
3. The server stores the update locally and in HDFS.
4. Once all expected hospitals submit, the server runs trust-weighted aggregation.
5. The global model is saved locally and uploaded to HDFS.
6. Dashboard charts update from stored metrics and API responses.

## Trust Mechanism

The server calculates trust from two signals:

```text
trust =
    0.7 * accuracy
    + 0.3 * consistency
```

Consistency is based on the standard deviation of a hospital's historical accuracy:

```text
consistency = 1 - np.std(historical_accuracies)
```

A stable and accurate hospital receives higher trust. Participation is still shown in the dashboard as an analytics metric, but it is not part of the Phase 2 trust formula.

Hospital C is configured as the malicious demo client. It can lower accuracy and inject noisy weights, which makes the trust ranking visibly separate reliable hospitals from suspicious ones.

## Backend API

Main FastAPI endpoints:

```text
GET  /                         health check
POST /upload                   receive hospital update
GET  /status                   connected hospitals and stored rounds
GET  /round                    current federated round
GET  /global_model             latest global model
GET  /metrics                  local metrics history
GET  /global_metrics           global accuracy history
GET  /analytics                historical metrics and participation
GET  /trust                    current trust scores
GET  /leaderboard              sorted trust leaderboard
GET  /dashboard_data           dashboard summary payload
GET  /hospital_status          hospital online status
GET  /hdfs_status              HDFS connection and artifact counts
POST /malicious_demo           dashboard-controlled malicious demo toggle
```

## Storage Design

The server writes runtime state atomically to:

```text
server/state.json
```

On startup it restores the current round, trust scores and components, global model, pending updates, metrics, and completed rounds. Restarting the server therefore continues from the last saved round.

Each round also has a self-contained artifact directory:

```text
artifacts/round_1/
  Hospital_A.json
  Hospital_B.json
  Hospital_C.json
  global_model.json
```

This repository makes a training run reproducible and easier to audit or debug.

Every hospital update is stored as JSON:

```text
server/storage/updates/round_1/Hospital_A.json
server/storage/updates/round_1/Hospital_B.json
server/storage/updates/round_1/Hospital_C.json
```

Every aggregated global model is stored as JSON:

```text
server/storage/models/global_round_1.json
server/storage/models/global_round_2.json
```

Metrics are stored as CSV:

```text
server/storage/metrics/metrics.csv
```

CSV schema:

```csv
round,hospital,accuracy,trust
```

## HDFS Integration

The project uses `/trustfl` as the HDFS root:

```text
/trustfl/updates
/trustfl/models
/trustfl/metrics
```

Hospital updates are uploaded to:

```text
/trustfl/updates/round_N/Hospital_X.json
```

Global models are uploaded to:

```text
/trustfl/models/global_round_N.json
```

Metrics are uploaded to:

```text
/trustfl/metrics/metrics.csv
```

This gives the project a Hadoop-backed audit trail for federated learning artifacts.

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install fastapi uvicorn streamlit streamlit-autorefresh scikit-learn pandas numpy requests
```

If using HDFS, make sure Hadoop is running and the project folders exist:

```bash
hdfs dfs -mkdir -p /trustfl/updates
hdfs dfs -mkdir -p /trustfl/models
hdfs dfs -mkdir -p /trustfl/metrics
```

## Running The Demo

Start the backend and dashboard:

```bash
./scripts/start_all.sh
```

Open the dashboard:

```text
http://127.0.0.1:8501
```

Run all hospital clients concurrently:

```bash
./scripts/run_hospitals.sh
```

The clients should run concurrently because the server aggregates only after all three hospitals upload for the current round.

## Clean Reset

Before a clean demo:

```bash
./scripts/stop_reset.sh
```

This stops FastAPI, Streamlit, and hospital clients, clears ports `8000` and `8501`, removes generated local artifacts, and clears generated HDFS files under `/trustfl`.

## Verifying Local Artifacts

After a full 5-round run:

```bash
find server/storage/updates -name "*.json" | wc -l
find server/storage/models -name "*.json" | wc -l
cat server/storage/metrics/metrics.csv
```

Expected output:

```text
15 hospital update JSON files
5 global model JSON files
metrics.csv with round, hospital, accuracy, and trust rows
```

## Verifying HDFS Artifacts

Check the HDFS root:

```bash
hdfs dfs -ls /trustfl
```

Show hospital updates:

```bash
hdfs dfs -ls -R /trustfl/updates
```

Show global models:

```bash
hdfs dfs -ls /trustfl/models
```

Show metrics:

```bash
hdfs dfs -cat /trustfl/metrics/metrics.csv
```

Optional Hadoop NameNode UI:

```text
http://localhost:9870
```

Navigate to `/trustfl` to show the stored updates, models, and metrics from the browser.

## Dashboard Demo Flow

1. Open `http://127.0.0.1:8501`.
2. Show current round, connected hospitals, global accuracy, and best trusted hospital.
3. Run `./scripts/run_hospitals.sh`.
4. Watch hospital cards update with accuracy and trust.
5. Show the trust ranking where Hospital C is penalized.
6. Show accuracy and trust evolution charts.
7. Show recent JSON updates and global model repository.
8. Click live HDFS verification to show distributed storage status.
9. Open Hadoop UI at `http://localhost:9870` and browse `/trustfl`.

## What This Demonstrates To Recruiters

- Backend API design with FastAPI.
- Practical ML workflow orchestration.
- Federated learning concepts implemented in code.
- Trust scoring and malicious client simulation.
- Distributed storage integration using Hadoop HDFS.
- Data persistence using JSON and CSV.
- Dashboard development with Streamlit and pandas.
- Automation with Bash scripts for repeatable demos.
- System design thinking across client, server, storage, and visualization layers.

## Future Improvements

- Replace simulated clients with real distributed machines.
- Add authentication for hospital uploads.
- Validate model update schemas with Pydantic.
- Store metrics in Hive and query dashboard cards from Hive.
- Add model version metadata and rollback support.
- Compare normal FedAvg against TrustFL aggregation quantitatively.
- Containerize server, dashboard, and clients with Docker.
