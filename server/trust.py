import numpy as np


def calculate_trust_components(
    update,
    trust_history,
    participation_count=None
):
    hospital = update["hospital"]
    accuracy = float(np.clip(update["accuracy"], 0, 1))
    scores = trust_history.get(hospital, [accuracy])
    consistency = float(np.clip(1 - np.std(scores), 0, 1))

    trust = (
        0.7 * accuracy +
        0.3 * consistency
    )

    return {
        "hospital": hospital,
        "accuracy": accuracy,
        "consistency": consistency,
        "trust": float(np.clip(trust, 0, 1))
    }


def calculate_trust(
    update,
    trust_history,
    participation_count=None
):
    return calculate_trust_components(
        update,
        trust_history,
        participation_count
    )["trust"]
