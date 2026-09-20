"""Check CI authentication without logging credentials or raw OAuth responses."""

import argparse
import json
import os
from pathlib import Path

import httpx


def rejection_message(response):
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    error = payload.get("error")
    if error == "invalid_grant":
        description = payload.get("error_description")
        expired = isinstance(description, str) and description.lower() == "refresh token expired"
        reason = "expired" if expired else "expired, revoked, or invalid"
        return f"Spotify refresh token is {reason} (invalid_grant). Sign in again and replace SPOTIFY_REFRESH_TOKEN."
    if error == "invalid_client":
        return "Spotify rejected the app credentials (invalid_client). Check SPOTIFY_AUTH_STRING and its Spotify app."
    return f"Spotify token request failed (HTTP {response.status_code}); response body withheld to protect credentials."


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-config", type=Path)
    args = parser.parse_args()
    from esporifai.config import get_settings
    from esporifai.utils import handle_authorization

    settings = get_settings()
    if args.public_config:
        # These are public OAuth inputs, never client secrets or tokens.
        args.public_config.write_text(json.dumps({
            "client_id": settings.spotify_client_id,
            "redirect_uri": settings.redirect_uri,
        }) + "\n")
    try:
        handle_authorization(save_files=True, force=True, settings=settings)
    except httpx.HTTPStatusError as exc:
        message = rejection_message(exc.response)
        print(message)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
                summary.write(message + "\n")
        return 1
    print("Spotify authentication succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
