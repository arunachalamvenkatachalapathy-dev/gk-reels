"""
Uploads a rendered mp4 to YouTube as a Short using the YouTube Data API v3.

Auth: OAuth2 refresh token flow (one-time manual setup, see README).
Required secrets (passed as env vars):
  YT_CLIENT_ID
  YT_CLIENT_SECRET
  YT_REFRESH_TOKEN
"""
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def get_youtube_client():
    client_id = os.environ["YT_CLIENT_ID"].strip().strip('"\'')
    client_secret = os.environ["YT_CLIENT_SECRET"].strip().strip('"\'')
    refresh_token = os.environ["YT_REFRESH_TOKEN"].strip().strip('"\'')
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    return build("youtube", "v3", credentials=creds)


def upload_short(video_path, title, description, tags=None):
    """Uploads video_path as a public YouTube Short. Returns the video id."""
    youtube = get_youtube_client()

    # '#Shorts' in title/description is what YouTube uses to route a
    # vertical <=3min video into the Shorts shelf.
    if "#shorts" not in title.lower() and "#shorts" not in description.lower():
        description = description.rstrip() + "\n\n#Shorts"

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags or ["GK", "SSC", "quiz", "generalknowledge"],
            "categoryId": "27",  # Education
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  YouTube upload progress: {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"  YouTube Short published: https://youtube.com/shorts/{video_id}")
    return video_id


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "output_test.mp4"
    upload_short(path, "Test GK Short", "Daily GK quiz. Comment your answer before the reveal!")
