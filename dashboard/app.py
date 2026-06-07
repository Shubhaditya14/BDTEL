from pathlib import Path

import pandas as pd
import requests
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

SERVER_URL = "http://127.0.0.1:8000"
PROJECT_DIR = Path(__file__).resolve().parents[1]
STORAGE_DIR = PROJECT_DIR / "server" / "storage"
ARTIFACTS_DIR = PROJECT_DIR / "artifacts"
METRICS_FILE = STORAGE_DIR / "metrics" / "metrics.csv"
UPDATES_DIR = STORAGE_DIR / "updates"
MODELS_DIR = STORAGE_DIR / "models"

if st_autorefresh is not None:
    st_autorefresh(
        interval=8000,
        key="refresh"
    )


def get_json(path, default, timeout=2):
    try:
        response = requests.get(
            f"{SERVER_URL}{path}",
            timeout=timeout
        )
        return response.json()
    except requests.RequestException:
        return default


def post_json(path, params):
    try:
        requests.post(
            f"{SERVER_URL}{path}",
            params=params,
            timeout=5
        )
    except requests.RequestException:
        pass


def load_metrics():
    if METRICS_FILE.exists():
        df = pd.read_csv(METRICS_FILE)
        return df.drop_duplicates(
            subset=["round", "hospital"],
            keep="last"
        )

    metrics = get_json("/metrics", [])
    return pd.DataFrame(metrics)


def latest_from_metrics(df):
    if df.empty:
        return {}, {}

    latest = (
        df.sort_values("round")
        .groupby("hospital")
        .tail(1)
    )

    updates = {
        row.hospital: {
            "round": int(row.round),
            "accuracy": float(row.accuracy)
        }
        for row in latest.itertuples()
    }

    trust_scores = {
        row.hospital: float(row.trust)
        for row in latest.itertuples()
        if hasattr(row, "trust")
    }

    return updates, trust_scores


st.title("TrustFL Dashboard")

df = load_metrics()
update_files = sorted(UPDATES_DIR.glob("round_*/*.json")) if UPDATES_DIR.exists() else []
model_files = sorted(MODELS_DIR.glob("global_round_*.json")) if MODELS_DIR.exists() else []
artifact_update_files = (
    sorted(ARTIFACTS_DIR.glob("round_*/Hospital_*.json"))
    if ARTIFACTS_DIR.exists()
    else []
)
artifact_model_files = (
    sorted(ARTIFACTS_DIR.glob("round_*/global_model.json"))
    if ARTIFACTS_DIR.exists()
    else []
)

server_data = get_json(
    "/dashboard_data",
    {
        "round": 1,
        "updates": {},
        "trust_scores": {},
        "trust_components": {}
    }
)

csv_updates, csv_trust_scores = latest_from_metrics(df)

updates = server_data.get("updates") or csv_updates
trust_scores = server_data.get("trust_scores") or csv_trust_scores
trust_components = server_data.get("trust_components") or {}

if not updates and csv_updates:
    updates = csv_updates

if not trust_scores and csv_trust_scores:
    trust_scores = csv_trust_scores

if not df.empty:
    current_round = max(
        int(server_data.get("round", 1)),
        int(df["round"].max()) + 1
    )
else:
    current_round = server_data.get("round", 1)

statuses = get_json(
    "/hospital_status",
    {
        "Hospital_A": "Offline",
        "Hospital_B": "Offline",
        "Hospital_C": "Offline"
    }
)

hdfs_status = {
    "connected": bool(update_files or model_files or METRICS_FILE.exists()),
    "updates_stored": len(update_files),
    "models_stored": len(model_files),
    "metrics_stored": 1 if METRICS_FILE.exists() else 0
}

global_df = (
    df.groupby("round", as_index=False)["accuracy"]
    .mean()
    .rename(columns={"accuracy": "global_accuracy"})
    if not df.empty
    else pd.DataFrame(columns=["round", "global_accuracy"])
)

latest_global_accuracy = 0

if not global_df.empty:
    latest_global_accuracy = global_df.iloc[-1]["global_accuracy"]

st.header("System Overview")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Current Round", current_round)

with col2:
    st.metric("Connected Hospitals", len(updates))

with col3:
    st.metric("Global Accuracy", f"{latest_global_accuracy:.2f}")

with col4:
    if trust_scores:
        best_hospital = max(
            trust_scores,
            key=trust_scores.get
        )
        st.metric("Best Trusted Hospital", best_hospital)
    else:
        st.metric("Best Trusted Hospital", "-")

st.caption(
    f"Metrics source: {METRICS_FILE} | "
    f"rows: {len(df)} | "
    f"artifacts: {len(artifact_update_files)} updates, "
    f"{len(artifact_model_files)} models"
)

if df.empty:
    st.error("No metrics loaded. Run ./scripts/run_hospitals.sh first.")
else:
    with st.expander("Raw Metrics Data", expanded=False):
        st.dataframe(df)

malicious = st.toggle(
    "Simulate Malicious Hospital"
)

post_json(
    "/malicious_demo",
    {
        "enabled": malicious
    }
)

server_data = get_json(
    "/dashboard_data",
    {
        "round": current_round,
        "updates": updates,
        "trust_scores": trust_scores,
        "trust_components": trust_components
    }
)

updates = server_data.get("updates") or updates
trust_scores = server_data.get("trust_scores") or trust_scores
trust_components = (
    server_data.get("trust_components")
    or trust_components
)

if not updates and csv_updates:
    updates = csv_updates

if not trust_scores and csv_trust_scores:
    trust_scores = csv_trust_scores

st.subheader("Hospital Status")

for hospital, status in statuses.items():
    if status == "Online":
        st.success(f"{hospital}: {status}")
    else:
        st.warning(f"{hospital}: {status}")

st.subheader("HDFS Status")

if hdfs_status["connected"]:
    st.success("HDFS Artifacts Available")
else:
    st.error("No HDFS artifacts found locally")

hdfs_col1, hdfs_col2, hdfs_col3 = st.columns(3)

with hdfs_col1:
    st.metric("Updates Stored", hdfs_status["updates_stored"])

with hdfs_col2:
    st.metric("Models Stored", hdfs_status["models_stored"])

with hdfs_col3:
    st.metric("Metrics Stored", hdfs_status["metrics_stored"])

if st.button("Verify Live HDFS Connection"):
    live_hdfs_status = get_json(
        "/hdfs_status",
        hdfs_status,
        timeout=30
    )

    if live_hdfs_status["connected"]:
        st.success("Live HDFS Connected")
    else:
        st.error("Live HDFS Not Connected")

    st.json(live_hdfs_status)

st.subheader("Hospital Metrics")

if updates:
    for hospital, info in updates.items():
        trust = trust_scores.get(hospital, 0)

        st.metric(
            label=hospital,
            value=f"{info['accuracy']:.2f}",
            delta=f"Trust {trust:.2f}"
        )
else:
    st.info("No hospital updates yet.")

st.subheader("Recent Updates")

if ARTIFACTS_DIR.exists():
    if artifact_update_files:
        for update_file in sorted(
            artifact_update_files,
            reverse=True
        )[:10]:
            st.write(
                f"{update_file.stem} - "
                f"{update_file.parent.name.replace('_', ' ').title()}"
            )
    else:
        st.info("No hospital artifacts yet.")
else:
    st.info("No artifact repository yet.")

st.subheader("Global Models")

if ARTIFACTS_DIR.exists():
    if artifact_model_files:
        for model_file in artifact_model_files:
            st.write(
                model_file.parent.name.replace("_", " ").title()
            )
    else:
        st.info("No global model artifacts yet.")
else:
    st.info("No artifact repository yet.")

st.subheader("Artifact Browser")

if ARTIFACTS_DIR.exists():
    round_dirs = sorted(
        [
            path
            for path in ARTIFACTS_DIR.glob("round_*")
            if path.is_dir()
        ],
        key=lambda path: int(path.name.split("_")[-1])
    )

    if round_dirs:
        for round_dir in round_dirs:
            with st.expander(
                round_dir.name.replace("_", " ").title()
            ):
                for artifact in sorted(round_dir.glob("*.json")):
                    st.write(artifact.name)
    else:
        st.info("No round artifacts yet.")
else:
    st.info("No artifact repository yet.")

st.subheader("Accuracy Evolution")

if not df.empty:
    st.line_chart(
        df.groupby("round")["accuracy"].mean()
    )
else:
    st.info("No metrics yet.")

st.subheader("Round History")

if not df.empty:
    round_history = (
        df.groupby("round")
        .agg(
            participating_hospitals=("hospital", "nunique"),
            average_accuracy=("accuracy", "mean"),
            average_trust=("trust", "mean")
        )
        .reset_index()
    )
    st.dataframe(round_history, hide_index=True)
else:
    st.info("No completed rounds yet.")

st.subheader("Participation")

if not df.empty:
    completed_rounds = max(int(df["round"].max()), 1)
    participation_df = (
        df.groupby("hospital")["round"]
        .nunique()
        .rename("rounds_participated")
        .reset_index()
    )
    participation_df["participation_rate"] = (
        participation_df["rounds_participated"]
        / completed_rounds
    )
    st.dataframe(participation_df, hide_index=True)
    st.bar_chart(
        participation_df.set_index("hospital")[
            "rounds_participated"
        ]
    )
else:
    st.info("No participation history yet.")

st.subheader("Trust Evolution")

if not df.empty and "trust" in df.columns:
    trust_pivot = df.pivot_table(
        index="round",
        columns="hospital",
        values="trust",
        aggfunc="last"
    )

    st.line_chart(trust_pivot)
else:
    st.info("No trust history yet.")

st.subheader("Hospital Accuracy Comparison")

if not df.empty:
    accuracy_pivot = df.pivot_table(
        index="round",
        columns="hospital",
        values="accuracy",
        aggfunc="last"
    )

    st.line_chart(accuracy_pivot)
else:
    st.info("No hospital accuracy data yet.")

st.subheader("Global Accuracy")

if not global_df.empty:
    st.line_chart(
        global_df.set_index("round")
    )
else:
    st.info("No global accuracy yet.")

leaderboard_rows = []

for hospital, info in updates.items():
    leaderboard_rows.append({
        "Hospital": hospital,
        "Trust": trust_scores.get(hospital, 0),
        "Accuracy": info.get("accuracy", 0)
    })

trust_df = pd.DataFrame(leaderboard_rows)

if not trust_df.empty:
    trust_df = trust_df.sort_values(
        by="Trust",
        ascending=False
    )

st.subheader("Hospital Leaderboard")

st.dataframe(trust_df, hide_index=True)

if trust_components:
    component_df = pd.DataFrame(
        list(trust_components.values())
    )
    st.subheader("Trust Score Breakdown")
    st.dataframe(component_df, hide_index=True)
