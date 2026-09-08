"""
Sends an automated post to the Telegram channel with links to YouTube Shorts, Instagram Reels, and Facebook Page.
"""
import os
import html
import requests


def send_telegram_update(day, slot, q, yt_url=None, ig_url=None, fb_url=None):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("WARNING: Telegram credentials not set -- skipping Telegram post.")
        return False

    q_text = html.escape(q.get("question", ""))
    options = q.get("options", {})
    opt_a = html.escape(str(options.get("A", "")))
    opt_b = html.escape(str(options.get("B", "")))
    opt_c = html.escape(str(options.get("C", "")))
    opt_d = html.escape(str(options.get("D", "")))

    links = []
    if yt_url:
        links.append(f"📺 <a href=\"{yt_url}\"><b>Watch on YouTube Shorts</b></a>")
    if ig_url:
        links.append(f"📸 <a href=\"{ig_url}\"><b>Watch on Instagram Reels</b></a>")
    if fb_url:
        links.append(f"👥 <a href=\"{fb_url}\"><b>Watch on Facebook</b></a>")

    links_str = "\n".join(links) if links else "Links updating shortly!"

    msg = (
        f"🎯 <b>100 Days of GK Snippets • Day {day:02d} (Part {slot}/4)</b>\n\n"
        f"❓ <b>{q_text}</b>\n\n"
        f"<b>A)</b> {opt_a}\n"
        f"<b>B)</b> {opt_b}\n"
        f"<b>C)</b> {opt_c}\n"
        f"<b>D)</b> {opt_d}\n\n"
        f"👇 <b>Watch the 18-second video & reveal:</b>\n"
        f"{links_str}\n\n"
        f"🎁 <i>Comment your answer & follow to win the Sunday study gift!</i>\n"
        f"💡 <b>GK Snippets</b> • Big Knowledge. Short Videos."
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        print("  Telegram channel notification posted successfully!")
        return True
    except Exception as e:
        print(f"  Telegram notification FAILED: {e}")
        return False
