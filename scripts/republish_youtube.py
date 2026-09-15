\"\"\"
Re-uploads a specific question video directly to YouTube Shorts
without duplicating Instagram or Facebook uploads.
Usage:
    python scripts/republish_youtube.py q0018
\"\"\"
import os
import sys
import json

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from upload_youtube import upload_short
from seo_agent import SEOAgent

DATA_PATH = os.path.join(BASE, "data", "questions_en.json")
STATE_PATH = os.path.join(BASE, "data", "state.json")
OUT_DIR = os.path.join(BASE, "output")


def main():
    target_id = sys.argv[1] if len(sys.argv) > 1 else "q0018"

    with open(DATA_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    with open(STATE_PATH, encoding="utf-8") as f:
        state = json.load(f)

    q = next((item for item in questions if item["id"] == target_id), None)
    if not q:
        print(f"Error: Question {target_id} not found in {DATA_PATH}")
        sys.exit(1)

    # Find video file in output or download release asset
    video_files = [
        os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
        if target_id in f and f.endswith(".mp4")
    ] if os.path.exists(OUT_DIR) else []

    if not video_files:
        print(f"Error: No rendered video found for {target_id} in {OUT_DIR}")
        print("Please render the video first or place it in the output folder.")
        sys.exit(1)

    video_path = video_files[0]
    print(f"Found video: {video_path}")

    # Generate metadata using SEO agent
    seo = SEOAgent()
    meta = seo.generate_metadata(q)
    title = meta["title"]
    description = meta["description"]
    tags = meta["tags"]

    print(f"Uploading to YouTube Shorts: {title}...")
    yt_id = upload_short(video_path, title, description, tags)
    print(f"Successfully uploaded! Video URL: https://youtube.com/shorts/{yt_id}")

    # Update state history
    history = state.get("published_history", [])
    history.append({
        "id": target_id,
        "yt_id": yt_id,
        "title": title,
        "day": state.get("current_day", 10),
        "slot": state.get("current_slot", 1)
    })
    state["published_history"] = history[-20:]
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    print("State updated with YouTube ID.")


if __name__ == "__main__":
    main()
