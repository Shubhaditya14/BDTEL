import csv
import json
import threading
from pathlib import Path

import numpy as np
from fastapi import FastAPI

try:
    from .hdfs_storage import count_hdfs_files
    from .hdfs_storage import HDFS_ROOT
    from .hdfs_storage import list_hdfs_path
    from .hdfs_storage import upload_global_model
    from .hdfs_storage import upload_metrics
    from .hdfs_storage import upload_update
    from .hive_analytics import query_hive_analytics
    from .trust import calculate_trust
    from .trust import calculate_trust_components
except ImportError:
    from hdfs_storage import count_hdfs_files
    from hdfs_storage import HDFS_ROOT
    from hdfs_storage import list_hdfs_path
    from hdfs_storage import upload_global_model
    from hdfs_storage import upload_metrics
    from hdfs_storage import upload_update
    from hive_analytics import query_hive_analytics
    from trust import calculate_trust
    from trust import calculate_trust_components

app = FastAPI()

EXPECTED_HOSPITALS = 3
EXPECTED_HOSPITAL_NAMES = [
    "Hospital_A",
    "Hospital_B",
    "Hospital_C"
]
SERVER_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SERVER_DIR.parent
STORAGE_DIR = SERVER_DIR / "storage"
UPDATES_DIR = STORAGE_DIR / "updates"
METRICS_DIR = STORAGE_DIR / "metrics"
MODELS_DIR = STORAGE_DIR / "models"
METRICS_FILE = METRICS_DIR / "metrics.csv"
STATE_FILE = SERVER_DIR / "state.json"
ARTIFACTS_DIR = PROJECT_DIR / "artifacts"

updates = {}
trust_history = {}
trust_scores = {}
trust_components = {}
global_model = None
current_round = 1
metrics = []
global_metrics = []
malicious_demo_enabled = False
state_lock = threading.Lock()
aggregated_rounds = set()


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = path.with_suffix(f"{path.suffix}.tmp")

    with open(temporary_file, "w") as file:
        json.dump(data, file, indent=4)

    temporary_file.replace(path)


def save_state():
    state = {
        "current_round": current_round,
        "trust_scores": trust_scores,
        "trust_components": trust_components,
        "global_model": global_model,
        "trust_history": trust_history,
        "updates": list(updates.values()),
        "metrics": metrics,
        "global_metrics": global_metrics,
        "aggregated_rounds": sorted(aggregated_rounds)
    }
    save_json(STATE_FILE, state)


def load_state():
    global current_round
    global global_model

    if not STATE_FILE.exists():
        return

    try:
        with open(STATE_FILE) as file:
            state = json.load(file)
    except (json.JSONDecodeError, OSError) as error:
        print(f"Could not load state: {error}")
        return

    current_round = int(state.get("current_round", 1))
    global_model = state.get("global_model")
    trust_scores.update(state.get("trust_scores", {}))
    trust_components.update(state.get("trust_components", {}))
    trust_history.update(state.get("trust_history", {}))
    metrics.extend(state.get("metrics", []))
    global_metrics.extend(state.get("global_metrics", []))
    aggregated_rounds.update(state.get("aggregated_rounds", []))

    for update in state.get("updates", []):
        updates[(update["hospital"], update["round"])] = update

    latest_updates = {}

    for (hospital, round_num), update in updates.items():
        if (
            hospital not in latest_updates
            or round_num > latest_updates[hospital]["round"]
        ):
            latest_updates[hospital] = update

    trust_scores.clear()
    trust_components.clear()

    for hospital, update in latest_updates.items():
        score_components = calculate_trust_components(
            update,
            trust_history
        )
        trust_components[hospital] = score_components
        trust_scores[hospital] = score_components["trust"]

    print(f"Restored server state at round {current_round}")


def participation_count(hospital):
    return len({
        round_num
        for stored_hospital, round_num in updates
        if stored_hospital == hospital
    })


def write_metrics_csv():
    METRICS_DIR.mkdir(parents=True, exist_ok=True)

    with open(METRICS_FILE, "w", newline="") as file:
        fieldnames = [
            "round",
            "hospital",
            "accuracy",
            "trust"
        ]
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(metrics)


load_state()


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
    update_key = (hospital, round_num)
    is_new_update = update_key not in updates

    updates[update_key] = update

    if hospital not in trust_history:
        trust_history[hospital] = []

    if is_new_update:
        trust_history[hospital].append(
            update["accuracy"]
        )

    score_components = calculate_trust_components(
        update,
        trust_history
    )
    trust_components[hospital] = score_components
    trust_scores[hospital] = score_components["trust"]
    trust = score_components["trust"]

    if is_new_update:
        metrics.append({
            "hospital": hospital,
            "accuracy": update["accuracy"],
            "round": round_num,
            "consistency": score_components["consistency"],
            "trust": trust
        })

    round_dir = UPDATES_DIR / f"round_{round_num}"
    round_dir.mkdir(parents=True, exist_ok=True)
    update_file = round_dir / f"{hospital}.json"
    save_json(update_file, update)

    artifact_round_dir = ARTIFACTS_DIR / f"round_{round_num}"
    save_json(
        artifact_round_dir / f"{hospital}.json",
        update
    )

    upload_update(update_file, round_num)

    write_metrics_csv()

    upload_metrics(METRICS_FILE)

    print(f"Received {hospital} Round {round_num}")

    round_updates = [
        update
        for (stored_hospital, stored_round), update in updates.items()
        if stored_round == round_num
    ]
    submitted_hospitals = {
        update["hospital"]
        for update in round_updates
    }

    if (
        round_num == current_round
        and len(round_updates) == EXPECTED_HOSPITALS
        and submitted_hospitals == set(EXPECTED_HOSPITAL_NAMES)
        and round_num not in aggregated_rounds
    ):
        run_aggregation(round_num)

    save_state()

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
        "round": current_round,
        "current_round": current_round
    }


@app.get("/metrics")
def get_metrics():
    return metrics


@app.get("/global_metrics")
def get_global_metrics():
    return global_metrics


@app.get("/analytics")
def analytics():
    participation = {
        hospital: participation_count(hospital)
        for hospital in EXPECTED_HOSPITAL_NAMES
    }

    return {
        "current_round": current_round,
        "completed_rounds": sorted(aggregated_rounds),
        "participation": participation,
        "metrics": metrics,
        "global_metrics": global_metrics
    }


@app.get("/hive_analytics")
def hive_analytics():
    return query_hive_analytics(METRICS_FILE)


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
        "trust_scores": get_display_trust_scores(),
        "trust_components": trust_components
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
            "trust": float(
                calculate_trust(
                    update,
                    trust_history
                )
            )
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
    biases = [
        np.array(update["bias"])
        for update in round_updates
    ]

    trust_scores = []

    for update in round_updates:
        trust_scores.append(
            calculate_trust(
                update,
                trust_history
            )
        )

    print("Trust Scores")

    for update in round_updates:
        print(
            update["hospital"],
            calculate_trust(
                update,
                trust_history
            )
        )

    trust_scores = np.array(trust_scores)

    weighted_sum = np.zeros_like(weights[0])
    weighted_bias_sum = np.zeros_like(biases[0])

    for w, b, t in zip(weights, biases, trust_scores):
        weighted_sum += w * t
        weighted_bias_sum += b * t

    global_weights = (
        weighted_sum /
        trust_scores.sum()
    )
    global_bias = (
        weighted_bias_sum /
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
        "weights": global_weights.tolist(),
        "bias": global_bias.tolist()
    }

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    model_file = MODELS_DIR / f"global_round_{round_num}.json"

    save_json(model_file, global_model)
    save_json(
        ARTIFACTS_DIR / f"round_{round_num}" / "global_model.json",
        global_model
    )

    upload_global_model(model_file)

    aggregated_rounds.add(round_num)
    current_round += 1
    save_state()

    print("Global Model Generated")

    return {
        "round": round_num,

        "trust_scores":
            trust_scores.tolist(),

        "global_weights":
            global_weights.tolist(),

        "global_bias":
            global_bias.tolist()
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
