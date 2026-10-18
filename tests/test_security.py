
import base64
import json
import os
import time
import unittest
from unittest.mock import patch

from device.security import create_token, verify_token


# Use a test-only secret. Never use this key in production.
TEST_SECRET = "test-secret-for-unit-tests-only-32-bytes-minimum"


class TestTokenSecurity(unittest.TestCase):

    def make_token(self, **kwargs):
        defaults = {
            "event_id": "test-event-001",
            "device_id": "test-device-001",
            "risk_level": "HIGH",
            "event_type": "UNEXPECTED_DOOR_OPEN",
            "secret": TEST_SECRET,
        }
        defaults.update(kwargs)
        return create_token(**defaults)

    def test_valid_token_is_accepted(self):
        token = self.make_token()

        payload = verify_token(
            token,
            secret=TEST_SECRET,
            max_age_seconds=300,
        )

        self.assertIsNotNone(payload)
        self.assertEqual(payload["event_id"], "test-event-001")
        self.assertEqual(payload["device_id"], "test-device-001")
        self.assertEqual(payload["risk_level"], "HIGH")

    def test_tampered_token_is_rejected(self):
        token = self.make_token()
        encoded_payload, encoded_signature = token.split(".")

        payload = json.loads(
            base64.urlsafe_b64decode(
                encoded_payload + "=" * (-len(encoded_payload) % 4)
            )
        )
        payload["risk_level"] = "LOW"

        changed_payload = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

        changed_encoded = base64.urlsafe_b64encode(
            changed_payload
        ).decode().rstrip("=")

        tampered_token = changed_encoded + "." + encoded_signature

        self.assertIsNone(
            verify_token(tampered_token, secret=TEST_SECRET)
        )

    def test_wrong_secret_is_rejected(self):
        token = self.make_token()

        self.assertIsNone(
            verify_token(token, secret="a-different-test-secret")
        )

    def test_expired_token_is_rejected(self):
        token = self.make_token()

        # Simulate a token issued more than 300 seconds ago.
        with patch("device.security.time.time", return_value=time.time() + 600):
            self.assertIsNone(
                verify_token(
                    token,
                    secret=TEST_SECRET,
                    max_age_seconds=300,
                )
            )

    def test_malformed_token_is_rejected(self):
     with self.assertRaises(ValueError):
        verify_token("this-is-not-a-valid-token", secret=TEST_SECRET)


if __name__ == "__main__":
    unittest.main()
