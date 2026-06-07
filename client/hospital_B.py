HOSPITAL_NAME = "Hospital_B"
ROUNDS = 5

print(f"Starting {HOSPITAL_NAME}")

import time

import numpy as np
import requests
from sklearn.datasets import load_breast_cancer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

BASE_URL = "http://127.0.0.1:8000"
UPLOAD_URL = f"{BASE_URL}/upload"

# Load dataset
data = load_breast_cancer()

X = data.data[200:400]
y = data.target[200:400]

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=100
)


def wait_for_round(round_num):
    while True:
        response = requests.get(f"{BASE_URL}/round")
        round_data = response.json()
        server_round = round_data.get(
            "round",
            round_data["current_round"]
        )

        if server_round >= round_num:
            return

        print(f"Waiting for round {round_num}")
        time.sleep(2)


def wait_for_global_model(round_num):
    while True:
        response = requests.get(f"{BASE_URL}/global_model")
        global_model = response.json()

        if global_model.get("round", 0) >= round_num:
            return global_model

        print(f"Waiting for global model from round {round_num}")
        time.sleep(2)


global_model = None

for round_num in range(1, ROUNDS + 1):
    wait_for_round(round_num)

    print(f"\n===== ROUND {round_num} =====")

    # Create model
    model = LogisticRegression(
        max_iter=5000,
        warm_start=True
    )

    if global_model is not None:
        model.coef_ = np.array(global_model["weights"])
        model.intercept_ = np.array(global_model["bias"])
        model.classes_ = np.unique(y_train)
        model.n_features_in_ = X_train.shape[1]

    # Train
    model.fit(X_train, y_train)

    # Predict
    predictions = model.predict(X_test)

    # Accuracy
    accuracy = accuracy_score(y_test, predictions)

    weights = model.coef_.tolist()
    bias = model.intercept_.tolist()

    hospital_update = {
        "hospital": HOSPITAL_NAME,
        "round": round_num,
        "accuracy": float(accuracy),
        "weights": weights,
        "bias": bias
    }

    print("\nHospital Update")
    print("----------------")
    print(hospital_update)

    print(f"{HOSPITAL_NAME} Accuracy: {accuracy:.4f}")

    response = requests.post(
        UPLOAD_URL,
        json=hospital_update
    )

    print("\nServer Response:")
    print(response.json())

    global_model = wait_for_global_model(round_num)

    print("\nDownloaded Global Model")
    print(global_model)
