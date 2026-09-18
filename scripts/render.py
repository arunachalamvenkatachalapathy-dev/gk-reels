"""
Renders the 1080x1920 vertical video for GK Reels using Playwright & FFmpeg.
Features:
- Ultra-high retention pacing (exact 9.5 - 10.5 seconds)
- Opening sensory sound hook to maximize Viewed vs. Swiped Away (VVSA)
- Dynamic 60 FPS countdown bar with synchronized ticking audio
- Celebration reveal chime & punchy voiceover rate (+22%)
"""
import os
import re
import sys
import json
import base64
import asyncio
import subprocess
import urllib.request
import urllib.error
from playwright.sync_api import sync_playwright
import edge_tts

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(BASE, "assets")
AUDIO_DIR = os.path.join(ASSETS, "audio")
TEMPLATE_PATH = os.path.join(BASE, "templates", "slide.html")

def _resolve_audio_file(*candidates):
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None

FALLBACK_MUSIC = _resolve_audio_file(
    os.path.join(AUDIO_DIR, "slot1_one_answer_left.mp3"),
    os.path.join(AUDIO_DIR, "track1_simplex.mp3"),
    os.path.join(ASSETS, "tension_bed.mp3")
)
REVEAL_DING = _resolve_audio_file(
    os.path.join(AUDIO_DIR, "celebration_pop.mp3"),
    os.path.join(ASSETS, "celebration_pop.mp3"),
    os.path.join(ASSETS, "reveal_ding.mp3")
)
COUNTDOWN_TICK = _resolve_audio_file(
    os.path.join(AUDIO_DIR, "countdown_tick.mp3"),
    os.path.join(ASSETS, "countdown_tick.mp3")
)
HOOK_SOUND = _resolve_audio_file(
    os.path.join(AUDIO_DIR, "hook_swoosh.mp3"),
    os.path.join(ASSETS, "hook_swoosh.mp3")
)

LETTERS = ["A", "B", "C", "D"]

TOPIC_BADGES = {
    "Ancient Indian History": ("⚔️ ANCIENT HISTORY", "#F59E0B", "rgba(245, 158, 11, 0.15)", "rgba(245, 158, 11, 0.45)"),
    "Medieval Indian History": ("🏰 MEDIEVAL HISTORY", "#EC4899", "rgba(236, 72, 153, 0.15)", "rgba(236, 72, 153, 0.45)"),
    "Modern Indian History & Freedom Struggle": ("🇮🇳 FREEDOM STRUGGLE", "#EF4444", "rgba(239, 68, 68, 0.15)", "rgba(239, 68, 68, 0.45)"),
    "Indian Polity & Constitution": ("🏛️ INDIAN POLITY", "#3B82F6", "rgba(59, 130, 246, 0.15)", "rgba(59, 130, 246, 0.45)"),
    "Geography & Environment": ("🌍 GEOGRAPHY", "#10B981", "rgba(16, 185, 129, 0.15)", "rgba(16, 185, 129, 0.45)"),
    "General Science & Everyday Tech": ("🧬 GENERAL SCIENCE", "#8B5CF6", "rgba(139, 92, 246, 0.15)", "rgba(139, 92, 246, 0.45)"),
    "Economics & Banking": ("📈 ECONOMY", "#06B6D4", "rgba(6, 182, 212, 0.15)", "rgba(6, 182, 212, 0.45)"),
    "Art, Culture & Literature": ("🎨 ART & CULTURE", "#F97316", "rgba(249, 115, 22, 0.15)", "rgba(249, 115, 22, 0.45)"),
    "General Knowledge": ("🎯 GENERAL KNOWLEDGE", "#F97316", "rgba(249, 115, 22, 0.15)", "rgba(249, 115, 22, 0.45)")
}


def _esc(text):
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))


def get_audio_duration(file_path):
    try:
        res = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        return 3.0


def build_html(question, options, correct_index, accent, show_answer=False, q_id="q0000", day=1, slot=1, topic_name=None, viral_badge=None):
    options_html = []
    for i, opt in enumerate(options):
        letter = LETTERS[i]
        is_correct = (i == correct_index)
        if show_answer:
            cls = "option correct" if is_correct else "option dimmed"
        else:
            cls = "option"
        options_html.append(
            f'<div class="{cls}">'
            f'<div class="option-badge">{letter}</div>'
            f'<div class="option-text">{_esc(opt)}</div>'
            f'</div>'
        )

    answer_tag = (
        '<div class="answer-tag">'
        '<span class="pop-emoji">✨</span>'
        '<span>CORRECT ANSWER REVEALED</span>'
        '<span class="pop-emoji">✨</span>'
        '</div>'
        '<div class="share-cta">💾 Save for Revision • Follow for Daily Quiz!</div>'
    ) if show_answer else ""
    timer_badge = '<span style="color: #F87171;">🔥 Time\'s Up!</span>' if show_answer else '<span>⏳ 3s Challenge</span>'

    badge_label = viral_badge if viral_badge else f"🔥 90% FAIL THIS"
    series_banner = (
        f'<div class="series-capsule">'
        f'<span class="series-sparkle">⚡</span>'
        f'<span class="series-title-text">{badge_label}</span>'
        f'<span class="series-divider">•</span>'
        f'<span class="series-day-pill">DAY {day:02d}</span>'
        f'<span class="series-sparkle">⚡</span>'
        f'</div>'
    )

    badge_data = TOPIC_BADGES.get(topic_name, ("🎯 GENERAL KNOWLEDGE", "#F97316", "rgba(249, 115, 22, 0.15)", "rgba(249, 115, 22, 0.45)"))
    cat_label, cat_color, cat_bg, cat_border = badge_data
    category_badge = f'<div class="category-pill" style="background: {cat_bg}; border: 1.5px solid {cat_border}; color: {cat_color};"><span>{cat_label}</span></div>'

    # Embed logo as Base64 data URI
    logo_path = os.path.join(ASSETS, "logo.jpg")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as lf:
            logo_b64 = base64.b64encode(lf.read()).decode("utf-8")
        logo_uri = f"data:image/jpeg;base64,{logo_b64}"
    else:
        logo_uri = ""

    q_size_class = "compact" if len(question) > 75 else ""

    tpl = open(TEMPLATE_PATH, encoding="utf-8").read()
    tpl = tpl.replace("{{ACCENT}}", accent)
    tpl = tpl.replace("{{SERIES_BANNER}}", series_banner)
    tpl = tpl.replace("{{TIMER_BADGE}}", timer_badge)
    tpl = tpl.replace("{{QUESTION_TRACKER}}", f"FAST-PACED QUIZ • PART {slot}")
    tpl = tpl.replace("{{CATEGORY_BADGE}}", category_badge)
    tpl = tpl.replace("{{Q_SIZE_CLASS}}", q_size_class)
    tpl = tpl.replace("{{QUESTION}}", _esc(question))
    tpl = tpl.replace("{{OPTIONS}}", "\n".join(options_html))
    tpl = tpl.replace("{{ANSWER_TAG}}", answer_tag)
    tpl = tpl.replace("{{LOGO_URI}}", logo_uri)
    return tpl


def screenshot_html(html_str, out_png, page):
    page.set_content(html_str, wait_until="load")
    page.screenshot(path=out_png)


def format_question_for_speech(text):
    s = text.strip()
    s = re.sub(r'\(s\)', 's', s)
    s = re.sub(r'\(es\)', 'es', s)
    if s.endswith(':'):
        s = s[:-1].strip() + '?'
    s = re.sub(r'([a-zA-Z0-9])\s+(Which\b|Choose\b|Select\b|What\b|In the context\b)', r'\1. \2', s, flags=re.IGNORECASE)
    s = re.sub(r'\s*(\d+)\.\s*', r', \1: ', s)
    s = re.sub(r'^,\s*', '', s)
    s = re.sub(r'[,:\s]+([,.])', r'\1', s)
    s = re.sub(r'\s{2,}', ' ', s)
    return s.strip()



# ── Fish Audio Voice Config (English Channel: Shah Rukh Khan) ────────────────
FISH_AUDIO_API_URL = "https://api.fish.audio/v1/tts"
# Shah Rukh Khan voice — most used English model (10,839 tasks)
FISH_VOICE_MODEL_ID = "1f51bb552a924f89837c80d6c1b11e03"
FISH_FALLBACK_MODEL_ID = "2eaa7cb1f3144f50880ea6a7e45c5499"  # backup SRK model


def _fish_audio_tts(text: str, out_path: str, api_key: str, model_id: str) -> bool:
    """
    Call Fish Audio TTS API and save the MP3 to out_path.
    Returns True on success, False on any failure.
    Fish Audio streams raw MP3 bytes — no special codec needed.
    """
    try:
        import json as _json
        payload = _json.dumps({
            "text": text,
            "reference_id": model_id,
            "format": "mp3",
            "mp3_bitrate": 128,
            "latency": "normal",
        }).encode("utf-8")

        req = urllib.request.Request(
            FISH_AUDIO_API_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        if len(data) < 500:
            print(f"  [Fish Audio] Response too small ({len(data)} bytes) — likely an error, skipping.")
            return False
        with open(out_path, "wb") as f:
            f.write(data)
        print(f"  [Fish Audio] OK Generated {os.path.basename(out_path)} ({len(data)//1024} KB)")
        return True
    except Exception as exc:
        print(f"  [Fish Audio] WARN Failed: {exc}")
        return False


async def generate_voiceover(question_text, answer_text, q_voice_path, ans_voice_path):
    """
    Generate voiceover MP3s.
    Primary: Fish Audio (Shah Rukh Khan voice) — vivid, energetic English narrator.
    Fallback: edge-tts en-IN-PrabhatNeural.
    """
    fish_api_key = os.environ.get("FISH_AUDIO_API_KEY", "")
    used_fish = False

    if fish_api_key:
        print("  [Fish Audio] Attempting Shah Rukh Khan voiceover...")
        ok_q = _fish_audio_tts(question_text, q_voice_path, fish_api_key, FISH_VOICE_MODEL_ID)
        ok_a = _fish_audio_tts(answer_text, ans_voice_path, fish_api_key, FISH_VOICE_MODEL_ID)
        if ok_q and ok_a:
            used_fish = True
        else:
            # Try backup SRK model before falling to edge-tts
            print("  [Fish Audio] Trying backup model...")
            ok_q = _fish_audio_tts(question_text, q_voice_path, fish_api_key, FISH_FALLBACK_MODEL_ID)
            ok_a = _fish_audio_tts(answer_text, ans_voice_path, fish_api_key, FISH_FALLBACK_MODEL_ID)
            if ok_q and ok_a:
                used_fish = True

    if not used_fish:
        print("  [Edge-TTS] Falling back to en-IN-PrabhatNeural...")
        voice = "en-IN-PrabhatNeural"
        comm_q = edge_tts.Communicate(question_text, voice, rate="+22%")
        await comm_q.save(q_voice_path)
        comm_ans = edge_tts.Communicate(answer_text, voice, rate="+24%")
        await comm_ans.save(ans_voice_path)
        print("  [Edge-TTS] OK Voiceover generated.")


def render_video(question_obj, accent, out_mp4, tmp_dir, bg_music=None, day=1, slot=1, topic_name=None, viral_badge=None):
    os.makedirs(tmp_dir, exist_ok=True)
    slide1_png = os.path.join(tmp_dir, "slide1.png")
    slide2_png = os.path.join(tmp_dir, "slide2.png")

    q_id = question_obj.get("id", "q0000")
    html1 = build_html(question_obj["question"], question_obj["options"],
                        question_obj["correct_index"], accent, show_answer=False, q_id=q_id, day=day, slot=slot, topic_name=topic_name, viral_badge=viral_badge)
    html2 = build_html(question_obj["question"], question_obj["options"],
                        question_obj["correct_index"], accent, show_answer=True, q_id=q_id, day=day, slot=slot, topic_name=topic_name, viral_badge=viral_badge)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        screenshot_html(html1, slide1_png, page)
        screenshot_html(html2, slide2_png, page)
        browser.close()

    correct_letter = LETTERS[question_obj["correct_index"]]
    correct_opt_text = question_obj["options"][question_obj["correct_index"]]
    
    opt_words = correct_opt_text.strip().split()
    clean_opt_text = " ".join(opt_words[:8]) if len(opt_words) > 10 else correct_opt_text
    ans_spoken_phrase = f"The correct answer is Option {correct_letter}: {clean_opt_text}."

    q_voice_mp3 = os.path.join(tmp_dir, "q_voice.mp3")
    ans_voice_mp3 = os.path.join(tmp_dir, "ans_voice.mp3")
    speech_q_text = format_question_for_speech(question_obj["question"])

    try:
        asyncio.run(generate_voiceover(speech_q_text, ans_spoken_phrase, q_voice_mp3, ans_voice_mp3))
        has_voice = True
    except Exception as e:
        print(f"Warning: Edge-TTS generation failed ({e}), falling back to music-only audio.")
        has_voice = False

    # Ultra-tight 9.5-10.5s Viral Pacing
    countdown_dur = 3.0
    if has_voice:
        q_dur = get_audio_duration(q_voice_mp3)
        ans_dur = get_audio_duration(ans_voice_mp3)
        slide1_time = round(min(7.5, max(6.5, q_dur + countdown_dur - 0.2)), 1)
        slide2_time = round(min(3.2, max(2.8, ans_dur + 0.5)), 1)
    else:
        slide1_time = 6.8
        slide2_time = 2.8

    total_time = round(slide1_time + slide2_time, 1)
    timer_start = round(slide1_time - countdown_dur, 2)
    ding_time = slide1_time
    ding_ms = int(ding_time * 1000)
    ans_ms = ding_ms + 200
    tick_ms = int(timer_start * 1000)

    # Dynamic animated countdown bar filter (60 FPS)
    video_only = os.path.join(tmp_dir, "video_only.mp4")
    vf_slide1 = (
        f"[0:v]fps=30,format=yuv420p,"
        f"drawbox=x=54:y=266:w='if(lt(t,{timer_start}), 972, max(0, 972*(1-(t-{timer_start})/{countdown_dur})))':"
        f"h=14:color='#F5A623':t=fill[v0];"
        f"[1:v]fps=30,format=yuv420p[v1];"
        f"[v0][v1]concat=n=2:v=1:a=0[v]"
    )

    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1", "-t", str(slide1_time), "-i", slide1_png,
        "-loop", "1", "-t", str(slide2_time), "-i", slide2_png,
        "-filter_complex", vf_slide1,
        "-map", "[v]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        video_only,
    ], check=True)

    music_file = bg_music if (bg_music and os.path.exists(bg_music)) else FALLBACK_MUSIC

    audio_inputs = ["-i", video_only]
    input_idx = 1
    filter_parts = []
    mix_labels = []

    # 1. Background Music
    if music_file and os.path.exists(music_file):
        audio_inputs.extend(["-i", music_file])
        filter_parts.append(
            f"[{input_idx}:a]atempo=1.20,atrim=0:{total_time},afade=t=out:st={total_time - 0.3}:d=0.3,volume=0.30[bg]"
        )
        mix_labels.append("[bg]")
        input_idx += 1

    # 2. Opening Audio Hook (0.45s at t=0)
    if HOOK_SOUND and os.path.exists(HOOK_SOUND):
        audio_inputs.extend(["-i", HOOK_SOUND])
        filter_parts.append(f"[{input_idx}:a]adelay=0|0,volume=1.4[hook]")
        mix_labels.append("[hook]")
        input_idx += 1

    # 3. Question Voice
    if has_voice and q_voice_mp3 and os.path.exists(q_voice_mp3):
        audio_inputs.extend(["-i", q_voice_mp3])
        filter_parts.append(f"[{input_idx}:a]adelay=150|150,volume=1.8[vq]")
        mix_labels.append("[vq]")
        input_idx += 1

    # 4. Countdown Ticking
    if COUNTDOWN_TICK and os.path.exists(COUNTDOWN_TICK):
        audio_inputs.extend(["-i", COUNTDOWN_TICK])
        filter_parts.append(f"[{input_idx}:a]adelay={tick_ms}|{tick_ms},volume=1.4[tick]")
        mix_labels.append("[tick]")
        input_idx += 1

    # 5. Celebration / Ding Chime on Answer Reveal
    if REVEAL_DING and os.path.exists(REVEAL_DING):
        audio_inputs.extend(["-i", REVEAL_DING])
        filter_parts.append(f"[{input_idx}:a]adelay={ding_ms}|{ding_ms},volume=1.6[ding]")
        mix_labels.append("[ding]")
        input_idx += 1

    # 6. Answer Voice
    if has_voice and ans_voice_mp3 and os.path.exists(ans_voice_mp3):
        audio_inputs.extend(["-i", ans_voice_mp3])
        filter_parts.append(f"[{input_idx}:a]adelay={ans_ms}|{ans_ms},volume=1.8[va]")
        mix_labels.append("[va]")
        input_idx += 1

    if mix_labels:
        filter_parts.append(
            f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=0:normalize=0[out]"
        )
        filter_str = ";".join(filter_parts)
        subprocess.run([
            "ffmpeg", "-y",
            *audio_inputs,
            "-filter_complex", filter_str,
            "-map", "0:v",
            "-map", "[out]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            out_mp4,
        ], check=True)
    else:
        subprocess.run([
            "ffmpeg", "-y",
            "-i", video_only,
            "-c:v", "copy",
            out_mp4,
        ], check=True)

    print(f"Successfully rendered viral video ({total_time}s): {out_mp4}")
    return out_mp4
