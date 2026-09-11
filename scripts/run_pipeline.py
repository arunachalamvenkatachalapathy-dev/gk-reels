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


def get_ist_date():
    """Return current date in Indian Standard Time (UTC+05:30)."""
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    return datetime.datetime.now(ist).date().isoformat()


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    questions = load_json(DATA_PATH)
    state = load_json(STATE_PATH)

    videos_per_day = state.get("videos_per_day", 2)
    today_ist = get_ist_date()
    last_date = state.get("last_published_date")
    current_day = state.get("current_day", 4)
    published_today = state.get("published_today_count", 0)

    # Support manual override via CLI --force or env FORCE_PUBLISH=true
    force = ("--force" in sys.argv) or (os.environ.get("FORCE_PUBLISH", "").lower() in ("true", "1"))

    # ── CALENDAR-DATE LOCKED PROGRESSION ─────────────────────────────────
    # A new Day number only unlocks when the calendar date changes in IST.
    if last_date != today_ist:
        # Brand new calendar day in India -> Advance day, reset slot to 1
        day = (current_day + 1) if last_date is not None else current_day
        slot = 1
        published_today = 0
    else:
        # Same calendar day in India
        if published_today >= videos_per_day and not force:
            print(f"Daily quota of {videos_per_day} videos already reached for today ({today_ist}, Day {current_day}).")
            print(f"Holding Day {current_day + 1} until tomorrow morning. Exiting gracefully without error.")
            return
        day = current_day
        slot = published_today + 1

    # Non-repetition question pick
    q = pick_next_question(questions, state)
    accent = next_accent(state)
    bg_music = get_slot_track(slot)

    today = datetime.date.today().isoformat()
    out_mp4 = os.path.join(OUT_DIR, f"{today}_{q['id']}.mp4")
    tmp_dir = os.path.join(OUT_DIR, f"tmp_{q['id']}")

    print(f"=== Publishing Day {day} (Part {slot}/{videos_per_day}) ===")
    print(f"Question ID: {q['id']}")
    print(f"Audio Track: {os.path.basename(bg_music)}")
    print(f"Rendering 18s Video with ~4.5s Buffer Outro...")

    render_video(q, accent, out_mp4, tmp_dir, bg_music=bg_music, day=day, slot=slot)

    have_youtube = all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))
    have_instagram = all(os.environ.get(k) for k in ("IG_ACCESS_TOKEN", "IG_USER_ID", "GITHUB_TOKEN", "GITHUB_REPOSITORY"))

    # ── SEO SUPER AGENT: Dynamic Optimization & History Retrieval ─────────
    seo_data = None
    try:
        from seo_agent import generate_seo
        yt_client = None
        if have_youtube:
            try:
                from upload_youtube import get_youtube_client
                yt_client = get_youtube_client()
            except Exception as ye:
                print(f"  [SEO Agent] Notice: YouTube client init skipped ({ye})")

        seo_data = generate_seo(
            q, day, slot,
            videos_per_day=videos_per_day,
            yt_client=yt_client,
            published_history=state.get("published_history", [])
        )
        print(f"  [SEO Agent] Topic: {seo_data['topic']}")
        print(f"  [SEO Agent] Optimized Title: {seo_data['title']}")
        print(f"  [SEO Agent] Tags: {len(seo_data['tags'])} tags generated")
    except Exception as se:
        print(f"  [SEO Agent] Fallback to standard metadata due to: {se}")

    if seo_data:
        title = seo_data["title"]
        caption = seo_data["description"]
        tags = seo_data["tags"]
        ig_caption = seo_data["ig_caption"]
        fb_caption = seo_data["fb_caption"]
    else:
        # High quality static fallback
        opts_preview = " | ".join([f"({chr(65+i)}) {opt}" for i, opt in enumerate(q.get("options", []))])
        title = f"{q['question'][:28].rsplit(' ', 1)[0]} | GK Questions and Answers #Shorts"
        caption = (
            f"❓ {q['question']}\n"
            f"👉 Drop your answer in the comments: {opts_preview}\n\n"
            f"🎯 100 Days of GK Snippets • Day {day:02d} (Part {slot}/{videos_per_day})\n\n"
            f"⏱️ Video Timeline:\n"
            f"00:00 🎯 Question Challenge\n"
            f"00:05 ⏳ 10s Timer Challenge\n"
            f"00:15 🎉 Correct Answer & Explanation\n\n"
            f"🏆 Target Exams: UPSC CSE | SSC CGL 2026 | RRB NTPC | NDA | CDS | State PSCs\n\n"
            f"🎁 SUNDAY GIVEAWAY: Like, Subscribe & Comment your answer daily to win exclusive study materials!\n"
            f"📄 Join Telegram for daily PDF notes & quiz alerts: @GK_Snippets\n\n"
            f"#Shorts #ShortsFeed #YouTubeShorts #GKQuiz #GeneralKnowledge #DailyGK #UPSC #SSCCGL"
        )
        tags = ["GK Snippets", "GK Quiz", "General Knowledge", "SSC CGL", "UPSC", "Shorts", "Daily GK"]
        ig_caption = caption
        fb_caption = caption

    if not have_youtube:
        print("WARNING: YouTube credentials not fully set -- skipping YouTube upload.")
    if not have_instagram:
        print("WARNING: Instagram credentials not fully set -- skipping Instagram upload.")

    yt_url = None
    ig_url = None
    fb_url = None

    if have_youtube:
        try:
            from upload_youtube import upload_short
            yt_id = upload_short(out_mp4, title, caption, tags=tags)
            if yt_id:
                yt_url = f"https://youtube.com/shorts/{yt_id}"
                # Record in state for SEO historical tracking
                history = state.get("published_history", [])
                history.append({
                    "id": q["id"],
                    "yt_id": yt_id,
                    "title": title,
                    "day": day,
                    "slot": slot
                })
                state["published_history"] = history[-20:]
        except Exception as e:
            print(f"  YouTube upload FAILED for {q['id']}: {e}")

    if have_instagram:
        try:
            from upload_instagram import upload_to_github_release, publish_reel
            tag_name = f"assets-{today}"
            public_url = upload_to_github_release(out_mp4, tag_name, os.path.basename(out_mp4))
            print(f"  Hosted at: {public_url}")
            _, ig_url = publish_reel(public_url, ig_caption)

            # Also publish directly to Facebook Page
            try:
                from upload_facebook import publish_facebook_video
                fb_id = publish_facebook_video(public_url, title, fb_caption)
                if fb_id:
                    page_id = os.environ.get("FB_PAGE_ID", "1268289243039491")
                    fb_url = f"https://www.facebook.com/{page_id}/videos/{fb_id}"
            except Exception as fe:
                print(f"  Facebook upload FAILED for {q['id']}: {fe}")
        except Exception as e:
            print(f"  Instagram upload FAILED for {q['id']}: {e}")

    # Send instant update to Telegram channel
    try:
        from upload_telegram import send_telegram_update
        send_telegram_update(day, slot, q, yt_url=yt_url, ig_url=ig_url, fb_url=fb_url)
    except Exception as te:
        print(f"  Telegram notification FAILED: {te}")

    # Advance state with strict non-repetition and calendar-date locking
    published_ids = state.get("published_ids", [])
    if q["id"] not in published_ids:
        published_ids.append(q["id"])
    state["published_ids"] = published_ids
    state["videos_per_day"] = videos_per_day
    state["total_published"] = state.get("total_published", 0) + 1
    state["last_published_date"] = today_ist
    state["published_today_count"] = published_today + 1
    state["current_day"] = day
    state["current_slot"] = slot

    save_json(STATE_PATH, state)
    print(f"Success! Published {q['id']} as Day {day} (Part {slot}/{videos_per_day}). Total published: {state['total_published']}.")


if __name__ == "__main__":
    main()
