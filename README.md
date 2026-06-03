# BDTEL MVP: TrustFL + HDFS Demo

This project simulates a Trust-Aware Federated Learning system with three hospitals, a FastAPI aggregation server, HDFS persistence, and a Streamlit dashboard.

## Project Layout

```text
client/
  hospital_A.py
  hospital_B.py
  hospital_C.py

server/
  server.py
  hdfs_storage.py
  trust.py
  storage/
    updates/
    metrics/
    models/

dashboard/
  app.py

scripts/
  start_all.sh
  start_server.sh
  start_dashboard.sh
  run_hospitals.sh
  stop_reset.sh
```

## What The Demo Shows

Each hospital trains locally on its own patient slice.

```text
Hospital_A -> first 200 patients
Hospital_B -> next 200 patients
Hospital_C -> remaining patients
```

Hospital C is configured as malicious:

```python
MALICIOUS = True
```

It lowers reported accuracy and injects noisy weights. The server uses trust-weighted aggregation so bad updates have less impact.

## HDFS Implementation

Every hospital upload is saved locally and pushed to HDFS:

```text
Hospital Update
  -> JSON
  -> server/storage/updates/round_N/Hospital_X.json
  -> /bdtelmvp/updates/round_N/Hospital_X.json
```

Every global model is saved locally and pushed to HDFS:

```text
Global Model
  -> JSON
  -> server/storage/models/global_round_N.json
  -> /bdtelmvp/models/global_round_N.json
```

Metrics are saved as CSV and pushed to HDFS:

```text
server/storage/metrics/metrics.csv
/bdtelmvp/metrics/metrics.csv
```

CSV schema:

```csv
round,hospital,accuracy,trust
```

## One-Command Reset

Use this before a clean demo:

```bash
./scripts/stop_reset.sh
```

This stops FastAPI, Streamlit, hospital clients, clears ports `8000` and `8501`, deletes local generated artifacts, and clears HDFS generated files under `/bdtelmvp`.

## Start The Demo

Start server and dashboard:

```bash
./scripts/start_all.sh
```

Open:

```text
http://127.0.0.1:8501
```

Run all three hospitals concurrently:

```bash
./scripts/run_hospitals.sh
```

Do not run the hospitals one after another. They must run concurrently because the server waits for all three hospitals before aggregating each round.

## Verify Local Storage

After the training run:

```bash
find server/storage/updates -name "*.json" | wc -l
find server/storage/models -name "*.json" | wc -l
cat server/storage/metrics/metrics.csv
```

Expected after 5 rounds:

```text
15 hospital update JSON files
5 global model JSON files
1 metrics.csv file
```

## Verify HDFS Storage

Check the HDFS project directory:

```bash
hdfs dfs -ls /bdtelmvp
```

Check hospital updates:

```bash
hdfs dfs -ls -R /bdtelmvp/updates
```

Expected:

```text
/bdtelmvp/updates/round_1/Hospital_A.json
/bdtelmvp/updates/round_1/Hospital_B.json
/bdtelmvp/updates/round_1/Hospital_C.json
...
/bdtelmvp/updates/round_5/Hospital_A.json
/bdtelmvp/updates/round_5/Hospital_B.json
/bdtelmvp/updates/round_5/Hospital_C.json
```

Check global models:

```bash
hdfs dfs -ls /bdtelmvp/models
```

Expected:

```text
global_round_1.json
global_round_2.json
global_round_3.json
global_round_4.json
global_round_5.json
```

Check metrics:

```bash
hdfs dfs -ls /bdtelmvp/metrics
hdfs dfs -cat /bdtelmvp/metrics/metrics.csv
```

## Panel-Friendly HDFS Showcase

Use `/bdtelmvp` everywhere for this project.

### Option 1: Show Every Hospital Update In HDFS

Each hospital update is stored as a JSON file.

Local file:

```text
server/storage/updates/round_1/Hospital_A.json
```

HDFS file:

```text
/bdtelmvp/updates/round_1/Hospital_A.json
```

Demo command:

```bash
hdfs dfs -ls /bdtelmvp/updates/round_1
```

Expected output:

```text
Hospital_A.json
Hospital_B.json
Hospital_C.json
```

Talking point:

```text
Every hospital model update is preserved in HDFS by round, creating an audit trail for federated learning.
```

### Option 2: Show Global Models In HDFS

After aggregation, the server writes one global model per round.

Local file:

```text
server/storage/models/global_round_1.json
```

HDFS file:

```text
/bdtelmvp/models/global_round_1.json
```

Demo command:

```bash
hdfs dfs -ls /bdtelmvp/models
```

Expected output:

```text
global_round_1.json
global_round_2.json
global_round_3.json
global_round_4.json
global_round_5.json
```

Talking point:

```text
The model repository keeps a versioned global model after every aggregation round.
```

### Option 3: Show Hadoop Web UI

Open:

```text
http://localhost:9870
```

In the NameNode web UI, browse the filesystem and navigate to:

```text
/bdtelmvp
```

Show these folders:

```text
updates/
models/
metrics/
```

Talking point:

```text
The browser UI confirms that TrustFL artifacts are stored in HDFS, not only local files.
```

### Option 4: Show Metrics CSV In HDFS

Metrics are stored as CSV so Hive can query them later.

HDFS file:

```text
/bdtelmvp/metrics/metrics.csv
```

Demo command:

```bash
hdfs dfs -cat /bdtelmvp/metrics/metrics.csv
```

Expected output:

```csv
round,hospital,accuracy,trust
1,Hospital_A,0.975,0.9825
1,Hospital_B,0.925,0.9475
1,Hospital_C,0.38823529411764707,0.571764705882353
```

Talking point:

```text
Metrics are stored in a Hive-friendly CSV format with round, hospital, accuracy, and trust.
```

## Dashboard Showcase

In the Streamlit dashboard, show:

```text
Current Round
Connected Hospitals
Global Accuracy
Best Trusted Hospital
HDFS Connected
Updates Stored
Models Stored
Metrics Stored
Trust Ranking
Round vs Accuracy
Trust Evolution
Hospital Accuracy Comparison
Recent Updates
Global Models
```

The important talking point:

```text
Hospital C sends malicious/noisy updates, but the TrustFL server assigns it lower trust and reduces its effect during aggregation.
```

## Useful API Endpoints

```text
http://127.0.0.1:8000/status
http://127.0.0.1:8000/round
http://127.0.0.1:8000/metrics
http://127.0.0.1:8000/trust
http://127.0.0.1:8000/hdfs_status
http://127.0.0.1:8000/dashboard_data
```

## Demo Script

1. Run `./scripts/stop_reset.sh`.
2. Run `./scripts/start_all.sh`.
3. Open the dashboard at `http://127.0.0.1:8501`.
4. Run `./scripts/run_hospitals.sh`.
5. Watch:
   - rounds advance,
   - hospital cards update,
   - trust ranking update,
   - HDFS counts increase,
   - model repository fill with global models.
6. Verify HDFS with `hdfs dfs -ls -R /bdtelmvp`.

## Notes

If the dashboard says FastAPI is unreachable, start the server:

```bash
./scripts/start_server.sh
```

If the dashboard does not auto-refresh, install:

```bash
pip install streamlit-autorefresh
```

The dashboard still works without that package; it just will not refresh automatically.
# BDTEL
