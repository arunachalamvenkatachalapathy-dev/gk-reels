import os
import sys
import json

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

# Ensure required YouTube credentials exist in environment
for var in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
    if not os.environ.get(var):
        token_file = os.path.join(BASE, "yt_token.json")
        if os.path.exists(token_file):
            try:
                with open(token_file, encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get(var.lower()):
                        os.environ[var] = data[var.lower()]
            except Exception:
                pass

from upload_youtube import upload_short
from seo_agent import generate_seo

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

    video_files = [
        os.path.join(OUT_DIR, f) for f in os.listdir(OUT_DIR)
        if target_id in f and f.endswith(".mp4")
    ] if os.path.exists(OUT_DIR) else []

    if not video_files:
        print(f"Error: No rendered video found for {target_id} in {OUT_DIR}")
        sys.exit(1)

    video_path = video_files[0]
    print(f"Found video: {video_path}")

    day = state.get("current_day", 10)
    slot = state.get("current_slot", 1)

    # Generate metadata using SEO agent
    seo_data = generate_seo(q, day, slot)
    title = seo_data["title"]
    description = seo_data["description"]
    tags = seo_data.get("tags", [])

    print(f"Uploading to YouTube Shorts: {title}...")
    yt_id = upload_short(video_path, title, description, tags)
    print(f"\n🎉 Successfully uploaded to YouTube Shorts!")
    print(f"URL: https://youtube.com/shorts/{yt_id}")

    # Update state history with yt_id
    history = state.get("published_history", [])
    for h in history:
        if h.get("id") == target_id:
            h["yt_id"] = yt_id
            break
    else:
        history.append({
            "id": target_id,
            "yt_id": yt_id,
            "title": title,
            "day": day,
            "slot": slot
        })
    state["published_history"] = history[-20:]
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    print("State updated with YouTube ID.")


if __name__ == "__main__":
    main()
