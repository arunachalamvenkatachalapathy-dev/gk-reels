"""Reconnect one GK YouTube channel without publishing a video.
Run on a laptop: python scripts/get_refresh_token.py
Secrets are saved locally with owner-only permissions, never printed.
"""
import getpass
import json
import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.readonly",
]

def main():
    client_id = input("Desktop OAuth client ID: ").strip()
    client_secret = getpass.getpass("Desktop OAuth client secret (hidden): ").strip()
    expected = input("Expected YouTube channel ID (UC...): ").strip()
    if not all((client_id, client_secret, expected)) or not expected.startswith("UC"):
        raise SystemExit("Client ID, secret and expected channel ID are required.")
    config = {"installed": {"client_id": client_id, "client_secret": client_secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token"}}
    flow = InstalledAppFlow.from_client_config(config, SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    channels = build("youtube", "v3", credentials=creds).channels().list(part="snippet", mine=True).execute().get("items", [])
    actual = [c["id"] for c in channels]
    for c in channels:
        print("Authorized channel:", c["snippet"]["title"], c["id"])
    if actual != [expected]:
        raise SystemExit("Wrong or ambiguous channel. No credentials saved. Re-run and choose the intended channel.")
    if not creds.refresh_token:
        raise SystemExit("No refresh token returned. Re-run with consent; do not upload.")
    folder = Path.home() / ".gk-oauth" / expected
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(folder, 0o700)
    for name, value in {"YT_CLIENT_ID": client_id, "YT_CLIENT_SECRET": client_secret, "YT_REFRESH_TOKEN": creds.refresh_token}.items():
        path = folder / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(value)
        os.chmod(path, 0o600)
    print("Channel verified. Credentials saved in", folder)
    print("Copy each file value only into the matching repo Actions secret. Never paste them into chat or commit them.")
    print("Delete the local credentials after the matching repository secrets are updated.")

if __name__ == "__main__":
    main()
