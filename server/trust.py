import numpy as np


def calculate_trust(update, trust_history):
    hospital = update["hospital"]
    accuracy = update["accuracy"]
    scores = trust_history[hospital]
    consistency = 1 - np.std(scores)

    trust = (
        0.7 * accuracy +
        0.3 * consistency
    )

    return trust
