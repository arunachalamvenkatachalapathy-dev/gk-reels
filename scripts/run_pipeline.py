"""
Entry point run by the GitHub Actions workflow, 4x per day.

For each run:
  1. Load data/state.json to see which question index we're up to.
  2. Take the next `videos_per_day` questions (wrapping around if we run
     past the end of the question bank).
  3. Render each as a 15s mp4 (templates/slide.html + Playwright + ffmpeg).
  4. Upload each to YouTube Shorts and Instagram Reels.
  5. Advance state.json past the questions we just used and commit it,
     so the next scheduled run picks up where this one left off.

If either platform's credentials are missing (e.g. you're still testing
the render step), that platform is skipped with a warning rather than
crashing the whole run -- so you can wire up YouTube and Instagram
independently.
"""
import os
import sys
import json
import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from render import render_video  # noqa: E402
from make_audio import make_tension_bed, make_reveal_ding  # noqa: E402

DATA_PATH = os.path.join(BASE, "data", "questions_en.json")
STATE_PATH = os.path.join(BASE, "data", "state.json")
OUT_DIR = os.path.join(BASE, "output")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def pick_batch(questions, state):
    n = state.get("videos_per_run", 1)
    total = len(questions)
    start = state["next_index"] % total
    batch = []
    for i in range(n):
        batch.append(questions[(start + i) % total])
    state["next_index"] = (start + n) % total
    return batch


def next_accent(state):
    palette = state["palette"]
    c = state["palette_cursor"] % len(palette)
    state["palette_cursor"] = (c + 1) % len(palette)
    return palette[c]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    make_tension_bed()
    make_reveal_ding()

    questions = load_json(DATA_PATH)
    state = load_json(STATE_PATH)
    batch = pick_batch(questions, state)

    today = datetime.date.today().isoformat()

    have_youtube = all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))
    have_instagram = all(os.environ.get(k) for k in ("IG_ACCESS_TOKEN", "IG_USER_ID", "GITHUB_TOKEN", "GITHUB_REPOSITORY"))

    if not have_youtube:
        print("WARNING: YouTube credentials not fully set -- skipping YouTube upload.")
    if not have_instagram:
        print("WARNING: Instagram credentials not fully set -- skipping Instagram upload.")

    for i, q in enumerate(batch):
        accent = next_accent(state)
        out_mp4 = os.path.join(OUT_DIR, f"{today}_{q['id']}.mp4")
        tmp_dir = os.path.join(OUT_DIR, f"tmp_{q['id']}")

        print(f"[{i+1}/{len(batch)}] Rendering {q['id']}: {q['question'][:60]}...")
        render_video(q, accent, out_mp4, tmp_dir)

        caption = (
            f"{q['question']}\n\n"
            f"Comment your answer below \U0001F447\n"
            f"Follow for daily SSC GK questions \U0001F514\n"
            f"Become a member for exclusive weekly updated PDFs \U0001F4C4\n\n"
            f"#GK #GeneralKnowledge #SSC #SSCCGL #QuizTime #Shorts"
        )

        if have_youtube:
            try:
                from upload_youtube import upload_short
                upload_short(out_mp4, q["question"][:95], caption)
            except Exception as e:
                print(f"  YouTube upload FAILED for {q['id']}: {e}")

        if have_instagram:
            try:
                from upload_instagram import upload_reel
                tag_name = f"assets-{today}"
                upload_reel(out_mp4, caption, tag_name, os.path.basename(out_mp4))
            except Exception as e:
                print(f"  Instagram upload FAILED for {q['id']}: {e}")

    save_json(STATE_PATH, state)
    print(f"Done. next_index now {state['next_index']}.")


if __name__ == "__main__":
    main()
