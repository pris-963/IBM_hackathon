
from typing import Any


def classify_risk(readings: dict[str, Any]) -> dict[str, Any]:
    """
    Classify a simulated environment as LOW, MEDIUM, or HIGH risk.

    Expected fields:
        door_open: bool
        unexpected_door_open: bool
        noise_db: float
        light_level: float (0-100)
        nearby_devices: int
    """

    required = {
        "door_open",
        "unexpected_door_open",
        "noise_db",
        "light_level",
        "nearby_devices",
    }

    missing = required - readings.keys()
    if missing:
        raise ValueError(f"Missing sensor fields: {sorted(missing)}")

    door_open = readings["door_open"]
    unexpected = readings["unexpected_door_open"]
    noise = readings["noise_db"]
    light = readings["light_level"]
    nearby = readings["nearby_devices"]

    if not isinstance(door_open, bool) or not isinstance(unexpected, bool):
        raise ValueError("Door fields must be boolean values.")

    if isinstance(noise, bool) or not isinstance(noise, (int, float)):
        raise ValueError("noise_db must be numeric.")

    if isinstance(light, bool) or not isinstance(light, (int, float)):
        raise ValueError("light_level must be numeric.")

    if isinstance(nearby, bool) or not isinstance(nearby, int):
        raise ValueError("nearby_devices must be an integer.")

    if not 0 <= noise <= 150:
        raise ValueError("noise_db must be between 0 and 150.")

    if not 0 <= light <= 100:
        raise ValueError("light_level must be between 0 and 100.")

    if nearby < 0:
        raise ValueError("nearby_devices cannot be negative.")

    score = 0
    reasons = []

    # An unexpected door opening is the strongest signal.
    if unexpected:
        score += 5
        reasons.append("Unexpected door opening")

    # Other signals provide context, not proof of danger.
    if noise >= 75:
        score += 1
        reasons.append("High ambient noise")

    if light < 15:
        score += 1
        reasons.append("Low light level")

    if nearby >= 20:
        score += 1
        reasons.append("High nearby-device count")

    if score >= 5:
        level = "HIGH"
    elif score >= 2:
        level = "MEDIUM"
    else:
        level = "LOW"

    if not reasons:
        reasons.append("No configured risk indicators detected")

    return {
        "risk_level": level,
        "risk_score": score,
        "reasons": reasons,
        "alert_required": level == "HIGH",
    }
