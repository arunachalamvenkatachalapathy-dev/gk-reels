"""
Entry point run by the GitHub Actions workflow, 4x per day.

Scheduled Runs (IST):
  - 08:00 IST -> Morning Drill (Part 1/4) -> slot1_one_answer_left.mp3
  - 13:00 IST -> Afternoon Drill (Part 2/4) -> slot2_the_final_second.mp3
  - 18:00 IST -> Evening Drill (Part 3/4) -> slot3_final_second_alt.mp3
  - 21:00 IST -> Night Revision (Part 4/4) -> slot4_heavy_hourglass.mp3

Features:
  1. Strict Non-Repetition: tracks published_ids, so no question is ever repeated.
  2. Day & Slot Sequencing: Day (total // 4) + 1, Slot (total % 4) + 1.
  3. 18-second video render with 3+ second buffer outro.
  4. Automatic rotation across user's 4 distinct tension tracks.
"""
import os
import sys
import json
import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from render import render_video  # noqa: E402

DATA_PATH = os.path.join(BASE, "data", "questions_en.json")
STATE_PATH = os.path.join(BASE, "data", "state.json")
OUT_DIR = os.path.join(BASE, "output")
AUDIO_DIR = os.path.join(BASE, "assets", "audio")

SLOT_TRACKS = {
    1: "slot1_one_answer_left.mp3",
    2: "slot2_the_final_second.mp3",
    3: "slot3_final_second_alt.mp3",
    4: "slot4_heavy_hourglass.mp3",
}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def pick_next_question(questions, state):
    published_ids = set(state.get("published_ids", []))
    
    # If all questions were used, reset cycle and start fresh revision
    if len(published_ids) >= len(questions):
        print("All questions in the bank published! Resetting cycle for round 2 revision.")
        published_ids = set()
        state["published_ids"] = []
        state["next_index"] = 0

    # Strictly sequential: iterate through the question bank in order (0 to 386)
    for i, q in enumerate(questions):
        if q["id"] not in published_ids:
            state["next_index"] = (i + 1) % len(questions)
            return q

    return questions[0]


def next_accent(state):
    palette = state.get("palette", ["#4D96FF", "#6BCB77", "#FFD93D", "#FF6B6B", "#A66DD4", "#FF9F45"])
    c = state.get("palette_cursor", 0) % len(palette)
    state["palette_cursor"] = (c + 1) % len(palette)
    return palette[c]


def get_slot_track(slot):
    filename = SLOT_TRACKS.get(slot, "slot1_one_answer_left.mp3")
    path = os.path.join(AUDIO_DIR, filename)
    if os.path.exists(path):
        return path
    # Fallback to any mp3
    tracks = [os.path.join(AUDIO_DIR, f) for f in os.listdir(AUDIO_DIR) if f.endswith(".mp3")]
    return tracks[0] if tracks else os.path.join(BASE, "assets", "tension_bed.mp3")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    questions = load_json(DATA_PATH)
    state = load_json(STATE_PATH)

    total_published = state.get("total_published", 0)
    day = (total_published // 4) + 1
    slot = (total_published % 4) + 1

    # Non-repetition question pick
    q = pick_next_question(questions, state)
    accent = next_accent(state)
    bg_music = get_slot_track(slot)

    today = datetime.date.today().isoformat()
    out_mp4 = os.path.join(OUT_DIR, f"{today}_{q['id']}.mp4")
    tmp_dir = os.path.join(OUT_DIR, f"tmp_{q['id']}")

    print(f"=== Publishing Day {day} (Part {slot}/4) ===")
    print(f"Question ID: {q['id']}")
    print(f"Audio Track: {os.path.basename(bg_music)}")
    print(f"Rendering 18s Video with ~4.5s Buffer Outro...")

    render_video(q, accent, out_mp4, tmp_dir, bg_music=bg_music, day=day, slot=slot)

    title = f"Day {day:02d} | 100 Days of GK Snippets 🎯 Daily Quiz #Shorts"
    caption = (
        f"✨ Day {day:02d} | 100 Days of GK Snippets\n\n"
        f"❓ {q['question']}\n\n"
        f"👇 Drop your answer in comments & Follow to win the Sunday Study Giveaway! 🎁\n"
        f"📄 Join Telegram for Exclusive Current Affairs PDFs & Memorization Tricks!\n\n"
        f"#gksnippets #gkquiz #generalknowledge #currentaffairs #dailygk #shorts #reels #quiz"
    )

    have_youtube = all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))
    have_instagram = all(os.environ.get(k) for k in ("IG_ACCESS_TOKEN", "IG_USER_ID", "GITHUB_TOKEN", "GITHUB_REPOSITORY"))

    if not have_youtube:
        print("WARNING: YouTube credentials not fully set -- skipping YouTube upload.")
    if not have_instagram:
        print("WARNING: Instagram credentials not fully set -- skipping Instagram upload.")

    if have_youtube:
        try:
            from upload_youtube import upload_short
            upload_short(out_mp4, title, caption)
        except Exception as e:
            print(f"  YouTube upload FAILED for {q['id']}: {e}")

    if have_instagram:
        try:
            from upload_instagram import upload_to_github_release, publish_reel
            tag_name = f"assets-{today}"
            public_url = upload_to_github_release(out_mp4, tag_name, os.path.basename(out_mp4))
            print(f"  Hosted at: {public_url}")
            publish_reel(public_url, caption)

            # Also publish directly to Facebook Page
            try:
                from upload_facebook import publish_facebook_video
                publish_facebook_video(public_url, title, caption)
            except Exception as fe:
                print(f"  Facebook upload FAILED for {q['id']}: {fe}")
        except Exception as e:
            print(f"  Instagram upload FAILED for {q['id']}: {e}")

    # Advance state with strict non-repetition
    published_ids = state.get("published_ids", [])
    if q["id"] not in published_ids:
        published_ids.append(q["id"])
    state["published_ids"] = published_ids
    state["total_published"] = total_published + 1
    state["current_day"] = ((total_published + 1) // 4) + 1
    state["current_slot"] = ((total_published + 1) % 4) + 1

    save_json(STATE_PATH, state)
    print(f"Success! Published {q['id']}. Next up: Day {state['current_day']} (Part {state['current_slot']}/4). Total published: {state['total_published']}.")


if __name__ == "__main__":
    main()
