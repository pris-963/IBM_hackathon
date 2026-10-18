
"""
Simulated IoT device for the Dynamic, Exposed-Only Safety Layer.

Features:
- Simulates safe, suspicious, and random sensor scenarios.
- Calculates risk using device.risk_engine when available.
- Generates HMAC-SHA256 signed event tokens.
- Sends HIGH-risk alerts to the FastAPI backend.
- Allows HTTP only for localhost; external URLs must use HTTPS.

Run from the project root:
    python device/simulator.py --scenario suspicious --count 5 \
        --send-url http://127.0.0.1:8000/alerts
"""

import argparse
import json
import os
import random
import sys
import time
import uuid

from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

# Support running this file directly from the project root.
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from device.security import create_token


DEVICE_ID = "SIM-DEVICE-001"
REQUEST_TIMEOUT_SECONDS = 10


def generate_readings(scenario):
    """Generate simulated sensor readings for the selected scenario."""

    if scenario == "safe":
        return {
            "door_open": False,
            "unexpected_door_open": False,
            "noise_db": round(random.uniform(20, 55), 1),
            "light_level": round(random.uniform(25, 100), 1),
            "nearby_devices": random.randint(0, 10),
        }

    if scenario == "suspicious":
        return {
            "door_open": True,
            "unexpected_door_open": True,
            "noise_db": round(random.uniform(10, 60), 1),
            "light_level": round(random.uniform(20, 100), 1),
            "nearby_devices": random.randint(20, 30),
        }

    if scenario == "random":
        door_open = random.choice([True, False])

        return {
            "door_open": door_open,
            "unexpected_door_open": (
                door_open and random.choice([True, False])
            ),
            "noise_db": round(random.uniform(10, 100), 1),
            "light_level": round(random.uniform(0, 100), 1),
            "nearby_devices": random.randint(0, 30),
        }

    raise ValueError(f"Unsupported scenario: {scenario}")


def calculate_risk(readings):
    """
    Calculate the risk score using the project's risk engine.

    If the risk engine exposes one of the supported function names,
    use it. Otherwise, apply the project's documented scoring rules.
    """

    try:
        from device import risk_engine

        for function_name in (
            "calculate_risk",
            "assess_risk",
            "evaluate_risk",
            "compute_risk",
            "get_risk",
        ):
            risk_function = getattr(
                risk_engine, function_name, None
            )

            if callable(risk_function):
                result = risk_function(readings)

                if isinstance(result, dict):
                    required = {
                        "risk_level",
                        "risk_score",
                        "reasons",
                        "alert_required",
                    }

                    if required.issubset(result):
                        return result

    except ImportError:
        pass

    # Fallback matching the documented risk_engine rules.
    score = 0
    reasons = []

    if readings.get("unexpected_door_open", False):
        score += 5
        reasons.append("Unexpected door opening")

    if readings.get("noise_db", 0) >= 75:
        score += 1
        reasons.append("High noise level")

    if readings.get("light_level", 100) < 15:
        score += 1
        reasons.append("Unusually low light level")

    if readings.get("nearby_devices", 0) >= 20:
        score += 1
        reasons.append("High nearby-device count")

    if score >= 5:
        risk_level = "HIGH"
    elif score >= 2:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "risk_level": risk_level,
        "risk_score": score,
        "reasons": reasons,
        "alert_required": risk_level == "HIGH",
    }


def validate_send_url(send_url):
    """Require HTTPS for non-local destinations."""

    parsed = urlparse(send_url)

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(
            "The send URL must be a valid HTTP or HTTPS URL."
        )

    hostname = parsed.hostname.lower()

    local_hosts = {
        "localhost",
        "127.0.0.1",
        "::1",
    }

    if hostname not in local_hosts and parsed.scheme != "https":
        raise ValueError(
            "HTTP is allowed only for localhost. "
            "Use HTTPS for external destinations."
        )

    return send_url


def send_alert(send_url, readings, risk_result, event_id, secret):
    """Create a signed event and send it to the backend."""

    if not send_url:
        print("No backend URL configured; alert was not sent.")
        return False

    validate_send_url(send_url)

    event_type = (
        "UNEXPECTED_DOOR_OPEN"
        if readings.get("unexpected_door_open", False)
        else "HIGH_RISK_SENSOR_EVENT"
    )

    token = create_token(
        event_id=event_id,
        device_id=DEVICE_ID,
        risk_level=risk_result["risk_level"],
        event_type=event_type,
        secret=secret,
    )

    payload = {
        "event_id": event_id,
        "device_id": DEVICE_ID,
        "risk_level": risk_result["risk_level"],
        "event_type": event_type,
        "token": token,
    }

    body = json.dumps(payload).encode("utf-8")

    request = Request(
        send_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            response_body = response.read().decode(
                "utf-8", errors="replace"
            )

            print(f"Backend HTTP status: {response.status}")

            if response_body:
                print("Backend response:", response_body)

            return 200 <= response.status < 300

    except HTTPError as exc:
        response_body = exc.read().decode(
            "utf-8", errors="replace"
        )

        print(f"Backend returned HTTP {exc.code}: {response_body}")
        return False

    except (URLError, TimeoutError, OSError) as exc:
        print(f"Could not send alert to backend: {exc}")
        return False


def run_simulation(scenario, send_url=None, count=1, delay=1.0):
    """Run the requested number of sensor simulations."""

    secret = os.getenv("DEVICE_SECRET")

    if send_url and not secret:
        raise RuntimeError(
            "DEVICE_SECRET is not set. Set the same secret used by "
            "the backend before running the simulator."
        )

    if send_url:
        validate_send_url(send_url)

    for index in range(count):
        print(f"\nScenario {index + 1}/{count}")
        print("\n--- Simulated device ---")

        print(f"Device: {DEVICE_ID}")
        print(
            "Time:",
            datetime.now(timezone.utc).isoformat(),
        )
        print(f"Scenario: {scenario}")

        readings = generate_readings(scenario)
        risk_result = calculate_risk(readings)

        print("Local readings:", json.dumps(readings, indent=2))
        print("Risk result:", json.dumps(risk_result, indent=2))

        if risk_result.get("alert_required", False):
            event_id = str(uuid.uuid4())

            print("HIGH-risk event detected.")

            if send_url:
                sent = send_alert(
                    send_url=send_url,
                    readings=readings,
                    risk_result=risk_result,
                    event_id=event_id,
                    secret=secret,
                )

                print(
                    "Alert sent successfully."
                    if sent
                    else "Alert was not accepted by the backend."
                )
            else:
                print(
                    "Alert required, but no --send-url was provided."
                )
        else:
            print("No alert required for this event.")

        if index < count - 1 and delay > 0:
            time.sleep(delay)


def main():
    parser = argparse.ArgumentParser(
        description="Simulate IoT sensor events and send risk alerts."
    )

    parser.add_argument(
        "--scenario",
        choices=["safe", "suspicious", "random"],
        default="random",
        help="Type of sensor scenario to simulate.",
    )

    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of simulations to run.",
    )

    parser.add_argument(
        "--send-url",
        default=None,
        help="Optional backend alert endpoint URL.",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between simulations.",
    )

    args = parser.parse_args()

    if args.count < 1:
        parser.error("--count must be at least 1.")

    if args.delay < 0:
        parser.error("--delay cannot be negative.")

    try:
        run_simulation(
            scenario=args.scenario,
            send_url=args.send_url,
            count=args.count,
            delay=args.delay,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
