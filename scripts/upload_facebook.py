"""
Publishes a rendered mp4 to the Facebook Page via the Graph API.
Uses the same public download URL hosted on GitHub Releases.
"""
import os
import requests

GRAPH = "https://graph.facebook.com/v20.0"


def publish_facebook_video(video_url, title, description):
    """Publishes a video to the Facebook Page using file_url."""
    page_id = os.environ.get("FB_PAGE_ID", "1268289243039491")
    token = os.environ["IG_ACCESS_TOKEN"]

    resp = requests.post(
        f"{GRAPH}/{page_id}/videos",
        data={
            "file_url": video_url,
            "title": title[:100],
            "description": description,
            "access_token": token,
        },
    )
    resp.raise_for_status()
    video_id = resp.json()["id"]
    print(f"  Facebook Page Video published: video id {video_id} (https://www.facebook.com/{page_id}/videos/{video_id})")
    return video_id
