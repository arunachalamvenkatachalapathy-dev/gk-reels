\"\"\"
Helper script to generate a fresh, long-lived YouTube OAuth Refresh Token.
Run this script locally on your computer:
    python scripts/get_refresh_token.py
\"\"\"
import sys

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("Installing google-auth-oauthlib...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-auth-oauthlib"])
    from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main():
    print("\n" + "=" * 60)
    print(" YouTube OAuth Refresh Token Generator")
    print("=" * 60)
    print("Please enter your Google Cloud OAuth Client ID & Secret:")
    client_id = input("Client ID: ").strip()
    client_secret = input("Client Secret: ").strip()

    if not client_id or not client_secret:
        print("\nError: Client ID and Client Secret cannot be empty.")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    print("\nOpening your browser for Google authentication...")
    print("Make sure you log into the Google Account owning the YouTube channel.\n")

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    creds = flow.run_local_server(port=0)

    print("\n" + "=" * 60)
    print(" AUTHENTICATION SUCCESSFUL!")
    print("=" * 60)
    print(f"\nYour new REFRESH TOKEN is:\n\n{creds.refresh_token}\n")
    print("=" * 60)
    print("Next Steps:")
    print("1. In Google Cloud Console -> OAuth consent screen -> Click 'PUBLISH APP'")
    print("   to switch from 'Testing' to 'In production' (prevents 7-day expiration).")
    print("2. Update the secret in GitHub Actions:")
    print(f'   gh secret set YT_REFRESH_TOKEN --body \"{creds.refresh_token}\"')
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
