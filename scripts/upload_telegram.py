"""
Sends an automated post to the Telegram channel using a 3-step engagement funnel:

  Step 1 — Telegram Quiz Poll (Strategy B): Options shown as poll answers for
            maximum in-channel interaction. Correct answer revealed only after voting.

  Step 2 — Curiosity Hook + Video Links (Strategy A + Current Setup):
            A teaser-style message (no full question text) funnels viewers to
            YouTube Shorts, Instagram Reels, or Facebook — whichever they prefer.

NO full video is uploaded. Links only — to maximise platform views.
"""
import os
import html
import requests


# ── helper ────────────────────────────────────────────────────────────────────

def _post(bot_token: str, method: str, payload: dict) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"  Telegram {method} FAILED: {e}")
        return False


# ── main entry point ───────────────────────────────────────────────────────────

def send_telegram_update(day, slot, q, yt_url=None, ig_url=None, fb_url=None):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id   = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("WARNING: Telegram credentials not set -- skipping Telegram post.")
        return False

    question      = q.get("question", "")
    options       = q.get("options", [])          # list of strings
    correct_index = q.get("correct_index", 0)     # 0-based int

    # ── STEP 1 — Telegram Quiz Poll (Strategy B) ───────────────────────────
    # Shows the full MCQ as an interactive Telegram quiz poll.
    # Users vote right inside the channel → big engagement spike.
    # Telegram reveals the correct answer only after each user votes.
    poll_question = f"🎯 Day {day:02d} | Part {slot}/4 — GK Snippets\n\n{question}"

    poll_payload = {
        "chat_id":          chat_id,
        "question":         poll_question[:300],   # Telegram cap: 300 chars
        "options":          options[:4],            # max 10, but we always have 4
        "type":             "quiz",
        "correct_option_id": correct_index,
        "is_anonymous":     True,                   # standard channel poll
        "explanation":      (
            "Watch the 18-second video explanation on YouTube Shorts, "
            "Instagram Reels, or Facebook! Links in the next message 👇"
        ),
        "explanation_parse_mode": "HTML",
    }

    ok_poll = _post(bot_token, "sendPoll", poll_payload)
    if ok_poll:
        print("  [Telegram] Quiz poll posted.")
    else:
        print("  [Telegram] Quiz poll failed — continuing with hook message.")

    # ── STEP 2 — Curiosity Hook + Video Links (Strategy A + Current Setup) ──
    # Does NOT repeat the question text (so people cannot paste it into Google).
    # Teaser copy creates FOMO / curiosity → forces click to watch the video.
    links = []
    if yt_url:
        links.append(f'📺 <a href="{yt_url}"><b>Watch on YouTube Shorts</b></a>')
    if ig_url:
        links.append(f'📸 <a href="{ig_url}"><b>Watch on Instagram Reels</b></a>')
    if fb_url:
        links.append(f'👥 <a href="{fb_url}"><b>Watch on Facebook</b></a>')

    links_str = "\n".join(links) if links else "Links updating shortly!"

    hook_msg = (
        f"🔍 <b>Did you get it right?</b>\n\n"
        f"⏱️ <i>The full 18-second explanation is live — pick your platform:</i>\n\n"
        f"{links_str}\n\n"
        f"🎁 <i>Comment your answer on the video &amp; follow to win the Sunday study gift!</i>\n"
        f"💡 <b>GK Snippets</b> • Big Knowledge. Short Videos."
    )

    hook_payload = {
        "chat_id":                  chat_id,
        "text":                     hook_msg,
        "parse_mode":               "HTML",
        "disable_web_page_preview": False,
    }

    ok_hook = _post(bot_token, "sendMessage", hook_payload)
    if ok_hook:
        print("  [Telegram] Curiosity hook + links posted.")
    else:
        print("  [Telegram] Hook message failed.")

    return ok_poll or ok_hook
