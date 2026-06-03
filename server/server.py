import csv
import json
import threading
from pathlib import Path

import numpy as np
from fastapi import FastAPI

try:
    from .hdfs_storage import count_hdfs_files
    from .hdfs_storage import list_hdfs_path
    from .hdfs_storage import upload_to_hdfs
    from .trust import calculate_trust
except ImportError:
    from hdfs_storage import count_hdfs_files
    from hdfs_storage import list_hdfs_path
    from hdfs_storage import upload_to_hdfs
    from trust import calculate_trust

app = FastAPI()

EXPECTED_HOSPITALS = 3
EXPECTED_HOSPITAL_NAMES = [
    "Hospital_A",
    "Hospital_B",
    "Hospital_C"
]
SERVER_DIR = Path(__file__).resolve().parent
STORAGE_DIR = SERVER_DIR / "storage"
UPDATES_DIR = STORAGE_DIR / "updates"
METRICS_DIR = STORAGE_DIR / "metrics"
MODELS_DIR = STORAGE_DIR / "models"
METRICS_FILE = METRICS_DIR / "metrics.csv"
HDFS_ROOT = "/bdtelmvp"

updates = {}
trust_history = {}
trust_scores = {}
global_model = None
current_round = 1
metrics = []
global_metrics = []
malicious_demo_enabled = False
state_lock = threading.Lock()
aggregated_rounds = set()


@app.get("/")
def home():
    return {"status": "alive"}


@app.post("/upload")
def upload(update: dict):
    with state_lock:
        return process_upload(update)


def process_upload(update: dict):
    hospital = update["hospital"]
    round_num = update["round"]

    updates[(hospital, round_num)] = update

    if hospital not in trust_history:
        trust_history[hospital] = []

    trust_history[hospital].append(
        update["accuracy"]
    )

    trust_scores[hospital] = float(
        calculate_trust(update, trust_history)
    )

    trust = trust_scores[hospital]

    metrics.append({
        "hospital": hospital,
        "accuracy": update["accuracy"],
        "round": round_num,
        "trust": trust
    })

    round_dir = UPDATES_DIR / f"round_{round_num}"
    round_dir.mkdir(parents=True, exist_ok=True)

    with open(
        round_dir / f"{hospital}.json",
        "w"
    ) as f:
        json.dump(update, f, indent=4)

    update_file = round_dir / f"{hospital}.json"
    upload_to_hdfs(
        update_file,
        f"{HDFS_ROOT}/updates/round_{round_num}/"
    )

    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    write_header = not METRICS_FILE.exists()

    with open(
        METRICS_FILE,
        "a",
        newline=""
    ) as f:
        writer = csv.writer(f)

        if write_header:
            writer.writerow([
                "round",
                "hospital",
                "accuracy",
                "trust"
            ])

        writer.writerow([
            round_num,
            hospital,
            update["accuracy"],
            trust
        ])

    upload_to_hdfs(
        METRICS_FILE,
        f"{HDFS_ROOT}/metrics/"
    )

    print(f"Received {hospital} Round {round_num}")

    round_updates = [
        update
        for (stored_hospital, stored_round), update in updates.items()
        if stored_round == round_num
    ]

    if (
        round_num == current_round
        and len(round_updates) == EXPECTED_HOSPITALS
        and round_num not in aggregated_rounds
    ):
        run_aggregation(round_num)

    return {"message": "Update received"}


@app.get("/status")
def status():
    hospitals = sorted({
        hospital
        for hospital, round_num in updates.keys()
    })

    rounds = sorted({
        round_num
        for hospital, round_num in updates.keys()
    })

    return {
        "connected_hospitals": len(hospitals),
        "stored_updates": len(updates),
        "hospitals": hospitals,
        "rounds": rounds
    }


@app.get("/round")
def round_info():

    return {
        "current_round": current_round
    }


@app.get("/metrics")
def get_metrics():
    return metrics


@app.get("/global_metrics")
def get_global_metrics():
    return global_metrics


@app.get("/trust")
def trust():
    return get_display_trust_scores()


@app.get("/hospital_status")
def hospital_status():

    return {
        hospital: "Online"
        for hospital in EXPECTED_HOSPITAL_NAMES
    }


@app.get("/hdfs_status")
def hdfs_status():
    result = list_hdfs_path(HDFS_ROOT)

    return {
        "connected": result.returncode == 0,
        "listing": result.stdout,
        "error": result.stderr,
        "updates_stored": count_hdfs_files(f"{HDFS_ROOT}/updates"),
        "models_stored": count_hdfs_files(f"{HDFS_ROOT}/models"),
        "metrics_stored": count_hdfs_files(f"{HDFS_ROOT}/metrics")
    }


@app.post("/malicious_demo")
def set_malicious_demo(enabled: bool):
    global malicious_demo_enabled

    malicious_demo_enabled = enabled

    return {
        "malicious_demo_enabled": malicious_demo_enabled,
        "trust_scores": get_display_trust_scores()
    }


@app.get("/dashboard_data")
def dashboard_data():
    latest_updates = {}

    for (hospital, round_num), update in updates.items():
        if (
            hospital not in latest_updates
            or round_num > latest_updates[hospital]["round"]
        ):
            latest_updates[hospital] = {
                "round": update["round"],
                "accuracy": update["accuracy"]
            }

    return {
        "round": current_round,
        "updates": latest_updates,
        "trust_scores": get_display_trust_scores()
    }


@app.get("/leaderboard")
def leaderboard():
    latest_updates = {}

    for (hospital, round_num), update in updates.items():
        if (
            hospital not in latest_updates
            or round_num > latest_updates[hospital]["round"]
        ):
            latest_updates[hospital] = update

    scores = [
        {
            "hospital": hospital,
            "trust": float(calculate_trust(update, trust_history))
        }
        for hospital, update in latest_updates.items()
    ]

    scores.sort(
        key=lambda score: score["trust"],
        reverse=True
    )

    return scores


def get_display_trust_scores():
    display_scores = trust_scores.copy()

    if malicious_demo_enabled and "Hospital_C" in display_scores:
        display_scores["Hospital_C"] = min(
            display_scores["Hospital_C"],
            0.31
        )

    return display_scores


def run_aggregation(round_num=None):
    global global_model
    global current_round

    print(updates)

    if not updates:
        return {
            "message": "No hospital updates available",
            "global_weights": []
        }

    if round_num is None:
        round_num = max(
            stored_round
            for hospital, stored_round in updates.keys()
        )

    if round_num in aggregated_rounds:
        return {
            "round": round_num,
            "message": "Round already aggregated",
            "global_model": global_model
        }

    round_updates = [
        update
        for (hospital, stored_round), update in updates.items()
        if stored_round == round_num
    ]

    if not round_updates:
        return {
            "message": f"No updates available for round {round_num}",
            "global_weights": []
        }

    weights = [
        np.array(update["weights"])
        for update in round_updates
    ]

    trust_scores = []

    for update in round_updates:
        trust_scores.append(
            calculate_trust(update, trust_history)
        )

    print("Trust Scores")

    for update in round_updates:
        print(
            update["hospital"],
            calculate_trust(update, trust_history)
        )

    trust_scores = np.array(trust_scores)

    weighted_sum = np.zeros_like(weights[0])

    for w, t in zip(weights, trust_scores):
        weighted_sum += w * t

    global_weights = (
        weighted_sum /
        trust_scores.sum()
    )

    global_accuracy = float(
        np.mean([
            update["accuracy"]
            for update in round_updates
        ])
    )

    global_metrics.append({
        "round": round_num,
        "global_accuracy": global_accuracy
    })

    global_model = {
        "round": round_num,
        "weights": global_weights.tolist()
    }

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    model_file = MODELS_DIR / f"global_round_{round_num}.json"

    with open(
        model_file,
        "w"
    ) as f:
        json.dump(
            global_model,
            f,
            indent=4
        )

    upload_to_hdfs(
        model_file,
        f"{HDFS_ROOT}/models/"
    )

    aggregated_rounds.add(round_num)
    current_round += 1

    print("Global Model Generated")

    return {
        "round": round_num,

        "trust_scores":
            trust_scores.tolist(),

        "global_weights":
            global_weights.tolist()
    }


@app.get("/aggregate")
def aggregate():
    return run_aggregation()


@app.get("/global_model")
def get_global_model():

    if global_model is None:
        return {
            "message": "No global model yet"
        }

    return global_model
