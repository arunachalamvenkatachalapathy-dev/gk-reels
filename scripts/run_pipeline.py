"""Render and publish two daily GK slots with persistent per-destination retry state."""
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


def is_suitable_short_question(q):
    text = q.get("question", "").strip()
    opts = q.get("options", [])
    if len(text.split()) > 22:
        return False
    if " 1. " in text and " 2. " in text:
        return False
    if any("1 and 2" in str(o) or "1, 2" in str(o) or "Both (a)" in str(o) or "None of the" in str(o) for o in opts):
        return False
    if any(len(str(o).split()) > 10 for o in opts):
        return False
    return True


def pick_next_question(questions, state, reviewed=None):
    """Pick the next unpublished question that has a source-checked entry.

    Unreviewed questions are never published and never marked published: they
    stay in the backlog and every skip is logged. If nothing reviewed remains,
    fail loudly so the buffer shortage is visible.
    """
    if reviewed is None:
        from render import REVIEWED as reviewed
    published_ids = set(state.get("published_ids", []))
    skipped = 0
    for i, q in enumerate(questions):
        if q["id"] in published_ids:
            continue
        if q["id"] not in reviewed:
            skipped += 1
            continue
        if skipped:
            print(f"NOTE: {skipped} unreviewed question(s) skipped (not published, not consumed); backlog unchanged.")
        state["next_index"] = (i + 1) % len(questions)
        return q
    raise RuntimeError(f"BUFFER EMPTY: no unpublished source-checked question remains ({skipped} unreviewed in backlog). Add reviewed entries before the next slot.")


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

    if not force and datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).hour < 15 and published_today >= 1:
        print("Morning slot already published; afternoon slot opens at 15:00 IST.")
        return

    if {"youtube", "instagram", "facebook"}.issubset(set(os.environ.get("PAUSED_DESTINATIONS", "").lower().split(","))):
        print("PAUSED: No active publishing destinations; question state unchanged.")
        return

    # Non-repetition question pick
    pending = state.get("pending_publication")
    if pending:
        if pending.get("date") != today_ist:
            raise RuntimeError("Unfinished publication from an earlier date; reconcile destinations before continuing.")
        q = next((item for item in questions if item["id"] == pending["question_id"]), None)
        if q is None:
            raise RuntimeError("Pending question is missing from the bank; manual reconciliation required.")
        day, slot = pending["day"], pending["slot"]
    else:
        q = pick_next_question(questions, state)
    accent = next_accent(state)
    bg_music = get_slot_track(slot)

    # Detect topic for category badge and branding
    topic_name = "General Knowledge & Daily Trivia"
    try:
        from seo_agent import detect_topic
        topic_name, _, _ = detect_topic(q.get("question", ""))
    except Exception:
        pass

    today = today_ist
    out_mp4 = os.path.join(OUT_DIR, f"{today}_{q['id']}.mp4")
    tmp_dir = os.path.join(OUT_DIR, f"tmp_{q['id']}")

    paused_destinations = set(os.environ.get("PAUSED_DESTINATIONS", "").lower().split(","))
    have_youtube = all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))
    have_youtube = have_youtube and "youtube" not in paused_destinations
    have_instagram = all(os.environ.get(k) for k in ("IG_ACCESS_TOKEN", "IG_USER_ID", "GITHUB_TOKEN", "GITHUB_REPOSITORY"))

    have_instagram = have_instagram and "instagram" not in paused_destinations

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

    viral_badge = None
    pinned_comment = None
    if seo_data:
        title = seo_data["title"]
        caption = seo_data["description"]
        tags = seo_data["tags"]
        ig_caption = seo_data["ig_caption"]
        fb_caption = seo_data["fb_caption"]
        viral_badge = seo_data.get("viral_badge")
        pinned_comment = seo_data.get("pinned_comment")
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
            f"#Shorts #ShortsFeed #YouTubeShorts #GKQuiz #GeneralKnowledge #DailyGK #UPSC #SSCCGL"
        )
        tags = ["GK Snippets", "GK Quiz", "General Knowledge", "SSC CGL", "UPSC", "Shorts", "Daily GK"]
        ig_caption = caption
        fb_caption = caption
        viral_badge = "DAILY GK QUIZ"
        pinned_comment = "Did you get it right before the timer? Drop your answer below! 👇"

    import re
    def safe_copy(text):
        text = re.sub(r"[^\n.!?]*\b(?:90|99)%[^\n.!?]*(?:[.!?]|$)", "", str(text), flags=re.I)
        lines = [line for line in text.splitlines() if not re.search(r"giveaway|free.*(?:notes|pdf)|pdf.*notes|win.*(?:gift|material)|गिवअवे|फ्री.*(?:नोट्स|PDF)|18[- ]second|00:\d\d", line, re.I)]
        return "\n".join(lines).replace("9 AM & 7 PM IST", "6 AM & 3 PM IST").replace("9 AM & 7 PM", "6 AM & 3 PM").replace("सुबह 9:00 और शाम 7:00 बजे", "सुबह 6:00 और दोपहर 3:00 बजे").strip() or ("Daily GK quiz" if DATA_PATH.endswith("questions_en.json") else "आज का GK सवाल")
    title, caption, ig_caption, fb_caption = map(safe_copy, (title, caption, ig_caption, fb_caption))
    viral_badge = "DAILY GK QUIZ" if DATA_PATH.endswith("questions_en.json") else "आज का GK सवाल"
    pinned_comment = "Comment your answer below." if DATA_PATH.endswith("questions_en.json") else "अपना उत्तर कमेंट करें।"

    print(f"=== Publishing Day {day} (Part {slot}/{videos_per_day}) ===")
    print(f"Question ID: {q['id']}")
    print(f"Topic: {topic_name}")
    print(f"Viral Badge: {viral_badge}")
    print(f"Audio Track: {os.path.basename(bg_music)}")
    print(f"Rendering Dynamic High-Retention Video (9.5-10.5s) with Animated Timer...")

    render_video(q, accent, out_mp4, tmp_dir, bg_music=bg_music, day=day, slot=slot, topic_name=topic_name, viral_badge=viral_badge)

    if not have_youtube:
        print("WARNING: YouTube credentials not fully set -- skipping YouTube upload.")
    if not have_instagram:
        print("WARNING: Instagram credentials not fully set -- skipping Instagram upload.")

    results = dict(pending.get("results", {})) if pending else {}
    yt_url = results.get("youtube")
    ig_url = results.get("instagram")
    fb_url = results.get("facebook")
    have_facebook = all(os.environ.get(k) for k in ("IG_ACCESS_TOKEN", "FB_PAGE_ID")) and "facebook" not in paused_destinations
    expected = [name for name, enabled in (("youtube", have_youtube), ("instagram", have_instagram), ("facebook", have_facebook)) if enabled]
    if not expected:
        raise RuntimeError("No publishing destination has complete credentials; question remains unpublished.")

    if have_youtube and not yt_url:
        try:
            from upload_youtube import upload_short
            yt_id = upload_short(out_mp4, title, caption, tags=tags, pinned_comment=pinned_comment)
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

    public_url = None
    if have_instagram and not ig_url:
        try:
            from upload_instagram import upload_to_github_release, publish_reel
            tag_name = f"assets-{today}"
            public_url = upload_to_github_release(out_mp4, tag_name, os.path.basename(out_mp4))
            print(f"  Hosted at: {public_url}")
            _, ig_url = publish_reel(public_url, ig_caption)
        except Exception as e:
            print(f"  Instagram upload FAILED for {q['id']}: {e}")

    # Publish to Facebook Page Reels (tab-specific Reels upload via Meta Graph API)
    if have_facebook and not fb_url:
        try:
            from upload_facebook import publish_facebook_reel
            fb_id = publish_facebook_reel(out_mp4, title, fb_caption, public_url=public_url)
            if fb_id:
                fb_url = f"https://www.facebook.com/reel/{fb_id}"
        except Exception as fe:
            print(f"  Facebook Reels upload FAILED for {q['id']}: {fe}")

    results.update({name: url for name, url in (("youtube", yt_url), ("instagram", ig_url), ("facebook", fb_url)) if url})
    missing = [name for name in expected if not results.get(name)]
    if missing:
        state["pending_publication"] = {"question_id": q["id"], "date": today_ist, "day": day, "slot": slot, "results": results}
        save_json(STATE_PATH, state)
        raise RuntimeError("Publication incomplete on: " + ", ".join(missing) + ". Successful destinations retained; retry will skip them.")
    state.pop("pending_publication", None)

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
