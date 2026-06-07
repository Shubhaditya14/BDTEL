import csv
import json
from pathlib import Path

import numpy as np
from sklearn.datasets import load_breast_cancer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


ROUNDS = 5
RESULTS_DIR = Path("experiments")
RESULTS_JSON = RESULTS_DIR / "results.json"
RESULTS_CSV = RESULTS_DIR / "results.csv"


def make_model(global_model, y_train, feature_count):
    model = LogisticRegression(
        max_iter=5000,
        warm_start=global_model is not None
    )

    if global_model is not None:
        model.coef_ = np.array(global_model["weights"])
        model.intercept_ = np.array(global_model["bias"])
        model.classes_ = np.unique(y_train)
        model.n_features_in_ = feature_count

    return model


def average_model(updates, trust_weighted):
    weights = [
        np.array(update["weights"])
        for update in updates
    ]
    biases = [
        np.array(update["bias"])
        for update in updates
    ]

    if trust_weighted:
        scores = np.array([
            update["trust"] ** 4
            for update in updates
        ])
    else:
        scores = np.ones(len(updates))

    weighted_weights = np.zeros_like(weights[0])
    weighted_biases = np.zeros_like(biases[0])

    for weights_value, bias_value, score in zip(
        weights,
        biases,
        scores
    ):
        weighted_weights += weights_value * score
        weighted_biases += bias_value * score

    return {
        "weights": (weighted_weights / scores.sum()).tolist(),
        "bias": (weighted_biases / scores.sum()).tolist()
    }


def evaluate_global_model(global_model, X_test, y_test):
    model = LogisticRegression()
    model.coef_ = np.array(global_model["weights"])
    model.intercept_ = np.array(global_model["bias"])
    model.classes_ = np.unique(y_test)
    model.n_features_in_ = X_test.shape[1]

    predictions = model.predict(X_test)
    return accuracy_score(y_test, predictions)


def consistency(history):
    return float(np.clip(1 - np.std(history), 0, 1))


def run_algorithm(name, trust_weighted):
    rng = np.random.default_rng(7)
    data = load_breast_cancer()
    X_train_all, X_test, y_train_all, y_test = train_test_split(
        data.data,
        data.target,
        test_size=0.2,
        random_state=42,
        stratify=data.target
    )
    scaler = StandardScaler()
    X_train_all = scaler.fit_transform(X_train_all)
    X_test = scaler.transform(X_test)

    hospitals = [
        ("Hospital_A", X_train_all[:150], y_train_all[:150], False),
        ("Hospital_B", X_train_all[150:300], y_train_all[150:300], False),
        ("Hospital_C", X_train_all[300:], y_train_all[300:], True)
    ]

    histories = {
        hospital: []
        for hospital, _, _, _ in hospitals
    }
    global_model = None
    round_results = []

    for round_num in range(1, ROUNDS + 1):
        updates = []

        for hospital, X_local, y_local, malicious in hospitals:
            model = make_model(
                global_model,
                y_local,
                X_local.shape[1]
            )
            model.fit(X_local, y_local)

            local_predictions = model.predict(X_test)
            accuracy = accuracy_score(y_test, local_predictions)
            weights = model.coef_.tolist()
            bias = model.intercept_.tolist()

            if malicious:
                accuracy *= 0.4
                weights = (
                    np.array(weights)
                    +
                    rng.normal(
                        0,
                        5,
                        np.array(weights).shape
                    )
                ).tolist()

            histories[hospital].append(accuracy)
            trust = (
                0.7 * accuracy
                +
                0.3 * consistency(histories[hospital])
            )

            updates.append({
                "hospital": hospital,
                "round": round_num,
                "accuracy": float(accuracy),
                "trust": float(trust),
                "weights": weights,
                "bias": bias
            })

        global_model = average_model(
            updates,
            trust_weighted=trust_weighted
        )
        global_accuracy = evaluate_global_model(
            global_model,
            X_test,
            y_test
        )
        round_results.append({
            "algorithm": name,
            "round": round_num,
            "global_accuracy": float(global_accuracy),
            "average_trust": float(np.mean([
                update["trust"]
                for update in updates
            ]))
        })

    return {
        "algorithm": name,
        "accuracy": round_results[-1]["global_accuracy"],
        "rounds": round_results
    }


def save_results(results):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    with open(RESULTS_JSON, "w") as file:
        json.dump(results, file, indent=4)

    with open(RESULTS_CSV, "w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "algorithm",
                "round",
                "global_accuracy",
                "average_trust"
            ]
        )
        writer.writeheader()

        for result in results:
            writer.writerows(result["rounds"])


def main():
    results = [
        run_algorithm("FedAvg", trust_weighted=False),
        run_algorithm("TrustFL", trust_weighted=True)
    ]
    save_results(results)

    fedavg = next(
        result
        for result in results
        if result["algorithm"] == "FedAvg"
    )
    trustfl = next(
        result
        for result in results
        if result["algorithm"] == "TrustFL"
    )

    print(f"FedAvg Accuracy: {fedavg['accuracy']:.2%}")
    print(f"TrustFL Accuracy: {trustfl['accuracy']:.2%}")
    print(f"Results saved to {RESULTS_JSON}")


if __name__ == "__main__":
    main()
