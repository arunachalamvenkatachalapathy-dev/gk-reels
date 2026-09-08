"""
Publishes a rendered mp4 to Instagram as a Reel via the Instagram Graph API.

Important constraint: Instagram's Content Publishing API does NOT accept a
raw file upload -- it needs a publicly reachable video_url it can fetch
from. Rather than paying for a CDN, this script uses a GitHub Release on
this same repo as free, instant public hosting: it uploads the mp4 as a
release asset, grabs the asset's public download URL, hands that URL to
Instagram, and once Instagram confirms the video was fetched, the release
asset has done its job (you can leave it -- GitHub storage is free and it
also acts as your own video archive/backup).

Required secrets (env vars):
  IG_ACCESS_TOKEN     long-lived Page access token with Instagram scopes
  IG_USER_ID          Instagram Business/Creator account id
  GITHUB_TOKEN        provided automatically inside GitHub Actions
  GITHUB_REPOSITORY   provided automatically inside GitHub Actions ("owner/repo")
"""
import os
import time
import requests

GRAPH = "https://graph.facebook.com/v20.0"


def _gh_headers():
    return {
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
    }


def upload_to_github_release(video_path, tag_name, asset_name):
    """Creates (or reuses) a release with tag_name and uploads video_path as an asset.
    Returns the public browser_download_url."""
    repo = os.environ["GITHUB_REPOSITORY"]
    api = f"https://api.github.com/repos/{repo}"

    # Create the release (ignore if it already exists today)
    resp = requests.post(
        f"{api}/releases",
        headers=_gh_headers(),
        json={"tag_name": tag_name, "name": tag_name, "body": "Automated reel asset drop.", "draft": False},
    )
    if resp.status_code == 201:
        release = resp.json()
    else:
        # already exists -> fetch it
        resp = requests.get(f"{api}/releases/tags/{tag_name}", headers=_gh_headers())
        resp.raise_for_status()
        release = resp.json()

    upload_url = release["upload_url"].split("{")[0]
    with open(video_path, "rb") as f:
        up = requests.post(
            f"{upload_url}?name={asset_name}",
            headers={**_gh_headers(), "Content-Type": "video/mp4"},
            data=f,
        )
    up.raise_for_status()
    return up.json()["browser_download_url"]


def publish_reel(video_url, caption):
    ig_user = os.environ["IG_USER_ID"]
    token = os.environ["IG_ACCESS_TOKEN"]

    # Step 1: create a media container
    create = requests.post(
        f"{GRAPH}/{ig_user}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": token,
        },
    )
    create.raise_for_status()
    container_id = create.json()["id"]

    # Step 2: poll until Instagram has finished fetching/processing the video
    status_url = f"{GRAPH}/{container_id}"
    for _ in range(30):  # up to ~5 minutes
        s = requests.get(status_url, params={"fields": "status_code", "access_token": token})
        s.raise_for_status()
        code = s.json().get("status_code")
        print(f"  Instagram container status: {code}")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise RuntimeError("Instagram failed to process the video container.")
        time.sleep(10)
    else:
        raise TimeoutError("Instagram container never reached FINISHED in time.")

    # Step 3: publish
    publish = requests.post(
        f"{GRAPH}/{ig_user}/media_publish",
        data={"creation_id": container_id, "access_token": token},
    )
    publish.raise_for_status()
    media_id = publish.json()["id"]
    print(f"  Instagram Reel published: media id {media_id}")

    permalink = "https://www.instagram.com/gksnippets/reels/"
    try:
        time.sleep(2)
        p_resp = requests.get(f"{GRAPH}/{media_id}", params={"fields": "permalink", "access_token": token})
        if p_resp.ok and p_resp.json().get("permalink"):
            permalink = p_resp.json()["permalink"]
    except Exception:
        pass

    return media_id, permalink


def upload_reel(video_path, caption, tag_name, asset_name):
    public_url = upload_to_github_release(video_path, tag_name, asset_name)
    print(f"  Hosted at: {public_url}")
    return publish_reel(public_url, caption)


if __name__ == "__main__":
    import sys, datetime
    path = sys.argv[1] if len(sys.argv) > 1 else "output_test.mp4"
    tag = "assets-" + datetime.date.today().isoformat()
    upload_reel(path, "Daily GK quiz. Comment your answer before the reveal! #Shorts", tag, os.path.basename(path))
