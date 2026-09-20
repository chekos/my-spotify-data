import importlib.util
from pathlib import Path
import unittest

import httpx

SPEC = importlib.util.spec_from_file_location(
    "check_spotify_auth", Path(__file__).resolve().parents[1] / "scripts/check_spotify_auth.py"
)
auth = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(auth)


class AuthDiagnosticsTest(unittest.TestCase):
    def test_expired_token_is_actionable(self):
        response = httpx.Response(400, json={"error": "invalid_grant", "error_description": "Refresh token expired"})
        self.assertIn("is expired (invalid_grant)", auth.rejection_message(response))

    def test_invalid_client_is_not_reported_as_expired_token(self):
        self.assertIn("app credentials", auth.rejection_message(httpx.Response(400, json={"error": "invalid_client"})))

    def test_arbitrary_response_content_never_appears_in_output(self):
        for payload in [{"error": "secret-token"}, {"error": "invalid_grant", "error_description": "secret-token"}, ["secret-token"]]:
            self.assertNotIn("secret-token", auth.rejection_message(httpx.Response(400, json=payload)))
        self.assertNotIn("secret-token", auth.rejection_message(httpx.Response(500, text="secret-token")))
