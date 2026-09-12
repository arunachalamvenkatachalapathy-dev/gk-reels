"""
Publishes a rendered mp4 to the Facebook Page Reels tab via the Meta Graph API.
Uses official 3-phase video_reels session endpoint for Page Reels:
1. upload_phase=start -> returns video_id and upload_url
2. binary upload to upload_url (OAuth token, offset 0, file_size)
3. upload_phase=finish -> video_state=PUBLISHED, description

Falls back to legacy /{page_id}/videos if Reels API returns an error.
"""
import os
import requests

GRAPH = "https://graph.facebook.com/v20.0"


def publish_facebook_reel(video_path, title, description, public_url=None):
    """
    Publishes a video to Facebook Page Reels using the 3-step video_reels API.
    If binary reels upload fails or file is missing, falls back to legacy /{page_id}/videos.
    """
    page_id = os.environ.get("FB_PAGE_ID", "1268289243039491")
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        print("  [Facebook] Skipped: IG_ACCESS_TOKEN environment variable not set")
        return None

    # Try official 3-step Facebook Reels API if local mp4 exists
    if video_path and os.path.isfile(video_path):
        file_size = os.path.getsize(video_path)
        try:
            print(f"  [Facebook Reels] Step 1/3: Initializing Reel session for Page {page_id}...")
            start_resp = requests.post(
                f"{GRAPH}/{page_id}/video_reels",
                params={
                    "upload_phase": "start",
                    "access_token": token,
                },
                timeout=30,
            )
            start_resp.raise_for_status()
            start_data = start_resp.json()
            video_id = start_data.get("video_id")
            upload_url = start_data.get("upload_url")

            if not video_id or not upload_url:
                raise ValueError(f"Invalid Reels session response: {start_data}")

            print(f"  [Facebook Reels] Step 2/3: Uploading binary payload ({file_size / (1024 * 1024):.2f} MB)...")
            with open(video_path, "rb") as f:
                headers = {
                    "Authorization": f"OAuth {token}",
                    "offset": "0",
                    "file_size": str(file_size),
                }
                upload_resp = requests.post(upload_url, headers=headers, data=f, timeout=120)
                upload_resp.raise_for_status()

            print(f"  [Facebook Reels] Step 3/3: Publishing Reel (video_id {video_id})...")
            finish_resp = requests.post(
                f"{GRAPH}/{page_id}/video_reels",
                params={
                    "upload_phase": "finish",
                    "access_token": token,
                    "video_id": video_id,
                    "video_state": "PUBLISHED",
                    "description": description,
                },
                timeout=30,
            )
            finish_resp.raise_for_status()
            print(f"  🎉 Facebook Reel published successfully!")
            print(f"  Reel URL: https://www.facebook.com/reel/{video_id}")
            return video_id
        except Exception as e:
            print(f"  [Facebook Reels] Notice: video_reels upload failed ({e}). Trying fallback to standard video...")

    # Fallback to standard Page video upload
    target_url = public_url if public_url else None
    if target_url:
        return publish_facebook_video(target_url, title, description)
    elif video_path and os.path.isfile(video_path):
        try:
            with open(video_path, "rb") as f:
                resp = requests.post(
                    f"{GRAPH}/{page_id}/videos",
                    data={
                        "title": title[:100],
                        "description": description,
                        "access_token": token,
                    },
                    files={"source": f},
                    timeout=120,
                )
                resp.raise_for_status()
                vid = resp.json().get("id")
                print(f"  Facebook Video fallback published: id {vid}")
                return vid
        except Exception as fe:
            print(f"  [Facebook] Direct video fallback failed: {fe}")
            return None
    else:
        print("  [Facebook] Error: No valid video_path or public_url provided")
        return None


def publish_facebook_video(video_url, title, description):
    """Publishes a video to the Facebook Page using file_url (Legacy feed endpoint)."""
    page_id = os.environ.get("FB_PAGE_ID", "1268289243039491")
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        print("  [Facebook] Skipped: IG_ACCESS_TOKEN environment variable not set")
        return None

    resp = requests.post(
        f"{GRAPH}/{page_id}/videos",
        data={
            "file_url": video_url,
            "title": title[:100],
            "description": description,
            "access_token": token,
        },
        timeout=60,
    )
    resp.raise_for_status()
    video_id = resp.json()["id"]
    print(f"  Facebook Page Video published: video id {video_id} (https://www.facebook.com/{page_id}/videos/{video_id})")
    return video_id
