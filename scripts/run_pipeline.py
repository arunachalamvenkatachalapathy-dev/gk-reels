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


def safe_error_message(exc):
    """Keep configured secrets out of exception logs."""
    message = str(exc)
    for name in (
        "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN", "IG_ACCESS_TOKEN", "GITHUB_TOKEN",
        "TELEGRAM_BOT_TOKEN", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "FISH_AUDIO_API_KEY",
    ):
        secret = os.environ.get(name)
        if secret:
            message = message.replace(secret, "[redacted]")
    return message


def is_suitable_short_question(q):
    text = q.get("question", "").strip()
    opts = q.get("options", [])
    if len(opts) < 2 or len(opts) > 4:
        return False
    return len(text) <= 120


def pick_next_question(questions, state):
    pending = state.get("pending_publication")
    if pending:
        today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).date().isoformat()
        if pending.get("date") != today:
            raise RuntimeError(f"Publication for earlier date {pending.get('date')} is incomplete; fix configuration and retry before today's slot")
        pending_id = pending.get("question_id")
        existing = next((q for q in questions if q.get("id") == pending_id), None)
        if not existing:
            raise RuntimeError(f"Pending question {pending_id!r} is not present in the English question bank")
        return existing
    published = set(state.get("published_ids", []))
    reviewed = set(state.get("reviewed_ids", []))
    used = published | set(state.get("in_progress_ids", []))
    candidates = [q for q in questions if q.get("id") not in used and q.get("id") in reviewed and is_suitable_short_question(q)]
    if not candidates:
        raise RuntimeError("BUFFER EMPTY: No unused reviewed, layout-safe questions are available for this slot.")
    return candidates[0]


def get_slot_track(slot):
    """Pick the cached SFX bundle that fits the current day slot."""
    # Prefer the dedicated track for this slot
    specific = os.path.join(AUDIO_DIR, SLOT_TRACKS.get(slot, ""))
    if os.path.exists(specific):
        return specific
    # Otherwise pick from the available pool deterministically
    tracks = [os.path.join(AUDIO_DIR, f) for f in os.listdir(AUDIO_DIR) if f.endswith(".mp3")]
    if not tracks:
        from make_audio import generate_audio
        generate_audio()
        tracks = [os.path.join(AUDIO_DIR, f) for f in os.listdir(AUDIO_DIR) if f.endswith(".mp3")]
    tracks.sort()
    return tracks[(slot - 1) % len(tracks)] if tracks else None


def next_accent(state):
    """Return and advance the deterministic colour rotation."""
    palette = state.get("palette", ["#3b82f6", "#ef4444", "#eab308", "#22c55e"])
    if not palette:
        palette = ["#3b82f6"]
    idx = int(state.get("accent_index", 0))
    state["accent_index"] = (idx + 1) % len(palette)
    return palette[idx % len(palette)]


def main():
    # Reload state and review marker on every run so scheduled calls see the latest approvals.
    questions = load_json(DATA_PATH)
    state = load_json(STATE_PATH)

    reviewed = state.get("reviewed_ids", [])
    if not reviewed:
        try:
            from render import REVIEWED
            reviewed = list(REVIEWED.keys())
        except Exception:
            reviewed = []

    pending = state.get("pending_publication")
    today_ist = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).date().isoformat()
    if pending and pending.get("date") != today_ist:
        raise RuntimeError(f"Pending publication is from {pending.get('date')}; will not advance or replace it with today's slot")
    videos_per_day = int(state.get("videos_per_day", 2))
    published_today = state.get("published_today_count", 0)

    if state.get("last_published_date") != today_ist:
        published_today = 0
        state["current_day"] = state.get("current_day", 1) + (1 if state.get("last_published_date") else 0)
        state["last_published_date"] = today_ist
    slot = published_today + 1
    day = state.get("current_day", 1)
    if slot > videos_per_day:
        print(f"Daily limit of {videos_per_day} videos reached.")
        return

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
    have_youtube = all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")) and "youtube" not in paused_destinations
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

    results = dict(pending.get("results", {})) if pending else {}
    yt_url = results.get("youtube")
    ig_url = results.get("instagram")
    fb_url = results.get("facebook")
    have_facebook = all(os.environ.get(k) for k in ("IG_ACCESS_TOKEN", "FB_PAGE_ID")) and "facebook" not in paused_destinations
    for platform, enabled, required in (
        ("YouTube", have_youtube, ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")),
        ("Instagram", have_instagram, ("IG_ACCESS_TOKEN", "IG_USER_ID", "GITHUB_TOKEN", "GITHUB_REPOSITORY")),
        ("Facebook", have_facebook, ("IG_ACCESS_TOKEN", "FB_PAGE_ID")),
    ):
        if enabled:
            print(f"[{platform}] CONFIGURED: upload will be attempted")
        elif platform.lower() in paused_destinations:
            print(f"[{platform}] SKIPPED: destination is paused")
        else:
            missing_credentials = [key for key in required if not os.environ.get(key)]
            print(f"[{platform}] SKIPPED: missing configuration: {', '.join(missing_credentials)}")
    if have_facebook and not fb_url:
        print(f"[Facebook] CONFIGURED: attempting Reels upload to FB_PAGE_ID={os.environ['FB_PAGE_ID']}")
    elif have_facebook and fb_url:
        print(f"[Facebook] SUCCESS (already recorded) type=reel url={fb_url}")
    expected = [name for name, enabled in (("youtube", have_youtube), ("instagram", have_instagram), ("facebook", have_facebook)) if enabled]
    if not expected:
        raise RuntimeError("No publishing destination has complete credentials; question remains unpublished.")

    if have_youtube and not yt_url:
        try:
            from upload_youtube import upload_short
            yt_id = upload_short(out_mp4, title, caption, tags=tags, pinned_comment=pinned_comment)
            if yt_id:
                yt_url = f"https://youtube.com/shorts/{yt_id}"
                print(f"[YouTube] SUCCESS url={yt_url}")
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
            else:
                print(f"[YouTube] FAILED: upload returned no video ID for {q['id']}")
        except Exception as e:
            print(f"[YouTube] FAILED for {q['id']}: {type(e).__name__}: {safe_error_message(e)}")
    elif have_youtube and yt_url:
        print(f"[YouTube] SUCCESS (already recorded) url={yt_url}")

    public_url = None
    if have_instagram and not ig_url:
        try:
            from upload_instagram import upload_to_github_release, publish_reel
            tag_name = f"assets-{today}"
            public_url = upload_to_github_release(out_mp4, tag_name, os.path.basename(out_mp4))
            print(f"  Hosted at: {public_url}")
            _, ig_url = publish_reel(public_url, ig_caption)
            if ig_url:
                print(f"[Instagram] SUCCESS type=reel url={ig_url}")
            else:
                print(f"[Instagram] FAILED: publish returned no media URL for {q['id']}")
        except Exception as e:
            print(f"[Instagram] FAILED for {q['id']}: {type(e).__name__}: {safe_error_message(e)}")
    elif have_instagram and ig_url:
        print(f"[Instagram] SUCCESS (already recorded) url={ig_url}")

    # Publish to Facebook Page Reels (tab-specific Reels upload via Meta Graph API)
    if have_facebook and not fb_url:
        try:
            from upload_facebook import publish_facebook_reel
            fb_id = publish_facebook_reel(out_mp4, title, fb_caption)
            if not fb_id:
                raise RuntimeError("Reels uploader returned no video ID")
            fb_url = f"https://www.facebook.com/reel/{fb_id}"
            print(f"[Facebook] SUCCESS type=reel id={fb_id} url={fb_url}")
        except Exception as fe:
            print(f"[Facebook] FAILED for {q['id']}: {type(fe).__name__}: {safe_error_message(fe)}")

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
