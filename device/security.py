
"""
Secure device-event tokens using HMAC-SHA256.
"""

import base64
import hashlib
import hmac
import json
import math
import time


DEFAULT_MAX_AGE_SECONDS = 300


def _secret_to_bytes(secret):
    """Convert a secret to bytes for HMAC."""
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    elif isinstance(secret, bytearray):
        secret = bytes(secret)

    if not isinstance(secret, bytes) or not secret:
        raise ValueError("Secret must be a non-empty string or bytes.")

    return secret


def _encode(data):
    """Encode bytes using URL-safe Base64 without padding."""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _decode(value):
    """Decode URL-safe Base64."""
    if not isinstance(value, str) or not value:
        raise ValueError("Invalid token encoding.")

    padding = "=" * (-len(value) % 4)

    try:
        return base64.b64decode(
            value + padding,
            altchars=b"-_",
            validate=True,
        )
    except Exception as exc:
        raise ValueError("Invalid token encoding.") from exc


def create_token(
    event_id,
    device_id,
    risk_level,
    event_type,
    secret,
    timestamp=None,
):
    """
    Create a signed token.

    timestamp is optional and defaults to the current Unix time.
    """

    secret = _secret_to_bytes(secret)

    if timestamp is None:
        timestamp = time.time()

    if (
        isinstance(timestamp, bool)
        or not isinstance(timestamp, (int, float))
        or not math.isfinite(timestamp)
    ):
        raise ValueError("timestamp must be a valid number.")

    payload = {
        "event_id": event_id,
        "device_id": device_id,
        "timestamp": timestamp,
        "risk_level": risk_level,
        "event_type": event_type,
    }

    for field, value in payload.items():
        if field == "timestamp":
            continue
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string.")

    message = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

    signature = hmac.new(
        secret,
        message,
        hashlib.sha256,
    ).digest()

    return f"{_encode(message)}.{_encode(signature)}"


def verify_token(
    token,
    secret,
    max_age_seconds=DEFAULT_MAX_AGE_SECONDS,
):
    """
    Verify a token.

    Returns the payload when valid.
    Returns None for invalid signatures or expired tokens.
    Raises ValueError for malformed tokens.
    """

    secret = _secret_to_bytes(secret)

    if (
        isinstance(max_age_seconds, bool)
        or not isinstance(max_age_seconds, int)
        or max_age_seconds <= 0
    ):
        raise ValueError("max_age_seconds must be a positive integer.")

    if not isinstance(token, str):
        raise ValueError("Token must be a string.")

    parts = token.split(".")
    if len(parts) != 2:
        raise ValueError("Malformed token.")

    encoded_payload, encoded_signature = parts

    message = _decode(encoded_payload)
    supplied_signature = _decode(encoded_signature)

    expected_signature = hmac.new(
        secret,
        message,
        hashlib.sha256,
    ).digest()

    # Wrong secret or modified payload.
    if not hmac.compare_digest(supplied_signature, expected_signature):
        return None

    try:
        payload = json.loads(message.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid token payload.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Token payload must be a dictionary.")

    required_fields = {
        "event_id",
        "device_id",
        "timestamp",
        "risk_level",
        "event_type",
    }

    if not required_fields.issubset(payload):
        raise ValueError("Token payload is missing required fields.")

    for field in ("event_id", "device_id", "risk_level", "event_type"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise ValueError(f"Invalid {field}.")

    timestamp = payload["timestamp"]

    if (
        isinstance(timestamp, bool)
        or not isinstance(timestamp, (int, float))
        or not math.isfinite(timestamp)
    ):
        raise ValueError("Invalid timestamp.")

    current_time = time.time()

    if timestamp > current_time + 30:
        return None

    if current_time - timestamp > max_age_seconds:
        return None

    return payload
