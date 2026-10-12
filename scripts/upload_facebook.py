"""
Publishes a rendered mp4 to the Facebook Page Reels tab via the Meta Graph API.
Uses official 3-phase video_reels session endpoint for Page Reels:
1. upload_phase=start -> returns video_id and upload_url
2. binary upload to upload_url (OAuth token, offset 0, file_size)
3. upload_phase=finish -> video_state=PUBLISHED, description

Never falls back to the legacy /videos endpoint; a Reel failure stays a failure.
"""
import os
import requests

GRAPH = "https://graph.facebook.com/v20.0"


def publish_facebook_reel(video_path, title, description, public_url=None):
    """
    Publishes a video to Facebook Page Reels using the 3-step video_reels API.
    Reels upload errors are surfaced to the caller. No standard-video fallback is used.
    """
    page_id = os.environ.get("FB_PAGE_ID")
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not page_id:
        print("  [Facebook] Skipped: missing FB_PAGE_ID secret")
        return None
    if not token:
        print("  [Facebook] Skipped: missing IG_ACCESS_TOKEN secret")
        return None
    if not video_path or not os.path.isfile(video_path):
        raise FileNotFoundError("Facebook Reels upload requires a local rendered video file")

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
                data={
                    "upload_phase": "finish",
                    "access_token": token,
                    "video_id": video_id,
                    "video_state": "PUBLISHED",
                    "description": description,
                    "title": title[:100] if title else "",
                },
                timeout=30,
            )
            finish_resp.raise_for_status()

            # Poll Meta transcoding status
            import time
            for attempt in range(6):
                time.sleep(3)
                try:
                    s_resp = requests.get(
                        f"{GRAPH}/{video_id}",
                        params={"fields": "status", "access_token": token},
                        timeout=15,
                    )
                    if s_resp.status_code == 200:
                        s_data = s_resp.json().get("status", {})
                        v_status = s_data.get("video_status")
                        print(f"  [Facebook Reels] Transcoding status: {v_status}")
                        if v_status == "ready":
                            break
                except Exception:
                    pass

            print(f"  🎉 Facebook Reel published successfully!")
            print(f"  Direct Reel URL: https://www.facebook.com/reel/{video_id}")
            print(f"  Page Reels Feed: https://www.facebook.com/{page_id}/reels")
            return video_id
    except Exception as e:
        raise RuntimeError(f"Facebook Reels upload failed: {e}") from e
