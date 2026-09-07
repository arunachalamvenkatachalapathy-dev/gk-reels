"""
Renders a high-retention quiz video from a question dict with guaranteed buffer outro.

Timing Architecture:
  - Slide 1 (Question + Countdown):
    * Duration dynamically adapts so question is fully read + at least 4.5s of thinking countdown.
    * For standard questions: exactly 10.0 seconds.
  - Slide 2 (Answer Reveal + 4.5s Buffer Outro):
    * Held for 8.0 seconds.
    * Chime Ding plays at the exact frame of slide transition.
    * Prabhat announces full answer (e.g. "The correct answer is Option A: Kosi").
    * 4.5+ seconds of buffer outro after answer narration finishes!
    * Smooth music fade-out at the final second.
"""
import os
import html
import asyncio
import edge_tts
from playwright.sync_api import sync_playwright
import subprocess

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.path.join(BASE, "templates", "slide.html")
ASSETS = os.path.join(BASE, "assets")
FALLBACK_MUSIC = os.path.join(ASSETS, "audio", "slot1_one_answer_left.mp3")
DING = os.path.join(ASSETS, "reveal_ding.mp3")

LETTERS = ["A", "B", "C", "D"]


def _esc(s):
    return html.escape(s, quote=False)


def get_audio_duration(path):
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path
        ]).decode().strip()
        return float(out)
    except Exception:
        return 3.5


def build_html(question, options, correct_index, accent, show_answer, q_id="q0000", day=1, slot=1):
    options_html = []
    for i, opt in enumerate(options):
        is_correct = (i == correct_index)
        cls = "option correct" if (show_answer and is_correct) else "option"
        check = '<span class="checkmark">&#10003;</span>' if (show_answer and is_correct) else ""
        options_html.append(
            f'<div class="{cls}">'
            f'<div class="letter">{LETTERS[i]}</div>'
            f'<div class="text">{_esc(opt)}</div>'
            f'{check}'
            f'</div>'
        )
    answer_tag = '<div class="answer-tag"><span>Answer Revealed</span></div>' if show_answer else ""
    timer_badge = "<span style=\"color: #F87171;\">🔥 Time's Up!</span>" if show_answer else "<span>⏳ 10s Challenge</span>"

    try:
        q_num = int(str(q_id).replace("q", "")) + 1
    except Exception:
        q_num = 1
    q_tracker = f"QUESTION #{q_num:03d} OF 387"
    series_banner = f"✨ 100 Days of GK Snippets • DAY {day:02d} (Part {slot}/4) ✨"

    tpl = open(TEMPLATE_PATH, encoding="utf-8").read()
    tpl = tpl.replace("{{ACCENT}}", accent)
    tpl = tpl.replace("{{SERIES_BANNER}}", series_banner)
    tpl = tpl.replace("{{TIMER_BADGE}}", timer_badge)
    tpl = tpl.replace("{{QUESTION_TRACKER}}", q_tracker)
    tpl = tpl.replace("{{QUESTION}}", _esc(question))
    tpl = tpl.replace("{{OPTIONS}}", "\n".join(options_html))
    tpl = tpl.replace("{{ANSWER_TAG}}", answer_tag)
    return tpl


def screenshot_html(html_str, out_png, page):
    page.set_content(html_str, wait_until="load")
    page.screenshot(path=out_png)


async def generate_voiceover(question_text, answer_text, q_voice_path, ans_voice_path):
    voice = "en-IN-PrabhatNeural"
    
    # 1. Question voiceover (brisk rate +12%)
    comm_q = edge_tts.Communicate(question_text, voice, rate="+12%")
    await comm_q.save(q_voice_path)

    # 2. Answer voiceover (energetic rate +16%)
    comm_ans = edge_tts.Communicate(answer_text, voice, rate="+16%")
    await comm_ans.save(ans_voice_path)


def render_video(question_obj, accent, out_mp4, tmp_dir, bg_music=None, day=1, slot=1):
    os.makedirs(tmp_dir, exist_ok=True)
    slide1_png = os.path.join(tmp_dir, "slide1.png")
    slide2_png = os.path.join(tmp_dir, "slide2.png")

    q_id = question_obj.get("id", "q0000")
    html1 = build_html(question_obj["question"], question_obj["options"],
                        question_obj["correct_index"], accent, show_answer=False, q_id=q_id, day=day, slot=slot)
    html2 = build_html(question_obj["question"], question_obj["options"],
                        question_obj["correct_index"], accent, show_answer=True, q_id=q_id, day=day, slot=slot)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        screenshot_html(html1, slide1_png, page)
        screenshot_html(html2, slide2_png, page)
        browser.close()

    # Generate voiceover for question and full answer
    correct_letter = LETTERS[question_obj["correct_index"]]
    correct_opt_text = question_obj["options"][question_obj["correct_index"]]
    
    # If option text is over 12 words, take first 10 words to fit cleanly
    opt_words = correct_opt_text.strip().split()
    clean_opt_text = " ".join(opt_words[:10]) if len(opt_words) > 12 else correct_opt_text
    ans_spoken_phrase = f"The correct answer is Option {correct_letter}: {clean_opt_text}."

    q_voice_mp3 = os.path.join(tmp_dir, "q_voice.mp3")
    ans_voice_mp3 = os.path.join(tmp_dir, "ans_voice.mp3")

    try:
        asyncio.run(generate_voiceover(question_obj["question"], ans_spoken_phrase, q_voice_mp3, ans_voice_mp3))
        has_voice = True
    except Exception as e:
        print(f"Warning: Edge-TTS generation failed ({e}), falling back to music-only audio.")
        has_voice = False

    # Calculate dynamic timing to guarantee zero cutoff & 4.5s buffer outro
    if has_voice:
        q_dur = get_audio_duration(q_voice_mp3)
        ans_dur = get_audio_duration(ans_voice_mp3)
        slide1_time = max(10, int(round(q_dur + 4.5)))
        slide2_time = 8  # 3.2s answer + 4.8s buffer outro
    else:
        slide1_time = 10
        slide2_time = 8

    total_time = slide1_time + slide2_time
    ding_time = slide1_time
    ding_ms = ding_time * 1000
    ans_ms = ding_ms + 200
    fade_start = total_time - 1

    # Build silent video track with exact dynamic slide hold durations
    video_only = os.path.join(tmp_dir, "video_only.mp4")
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1", "-t", str(slide1_time), "-i", slide1_png,
        "-loop", "1", "-t", str(slide2_time), "-i", slide2_png,
        "-filter_complex",
        "[0:v]fps=30,format=yuv420p[v0];[1:v]fps=30,format=yuv420p[v1];[v0][v1]concat=n=2:v=1:a=0[v]",
        "-map", "[v]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        video_only,
    ], check=True)

    # Pick background music track
    music_file = bg_music if (bg_music and os.path.exists(bg_music)) else FALLBACK_MUSIC

    if has_voice:
        # Mix with dynamic synchronization:
        # - Question voice at 0.3s
        # - Chime ding at exact transition frame (ding_ms)
        # - Full answer spoken at ans_ms
        # - 4.5s buffer outro with music fade at final second
        filter_str = (
            f"[1:a]atrim=0:{total_time},atempo=1.15,afade=t=out:st={fade_start}:d=1,volume=0.3[bg];"
            f"[2:a]adelay=300|300,volume=1.8[vq];"
            f"[3:a]adelay={ding_ms}|{ding_ms},volume=1.5[ding];"
            f"[4:a]adelay={ans_ms}|{ans_ms},volume=1.8[va];"
            f"[bg][vq][ding][va]amix=inputs=4:duration=first:dropout_transition=0:normalize=0[out]"
        )
        subprocess.run([
            "ffmpeg", "-y",
            "-i", video_only,
            "-i", music_file,
            "-i", q_voice_mp3,
            "-i", DING,
            "-i", ans_voice_mp3,
            "-filter_complex", filter_str,
            "-map", "0:v", "-map", "[out]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-t", str(total_time),
            out_mp4,
        ], check=True)
    else:
        # Fallback music-only mix
        filter_str = (
            f"[1:a]atempo=1.15,afade=t=out:st={fade_start}:d=1,volume=0.85[music];"
            f"[2:a]adelay={ding_ms}|{ding_ms},volume=1.4[ding];"
            f"[music][ding]amix=inputs=2:duration=first:dropout_transition=0[out]"
        )
        subprocess.run([
            "ffmpeg", "-y",
            "-i", video_only,
            "-t", str(total_time), "-i", music_file,
            "-i", DING,
            "-filter_complex", filter_str,
            "-map", "0:v", "-map", "[out]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-t", str(total_time),
            out_mp4,
        ], check=True)

    return out_mp4


if __name__ == "__main__":
    import json, sys
    q = {
        "id": "q0001",
        "question": "Which river is known as the 'Sorrow of Bihar'?",
        "options": ["Kosi", "Gandak", "Son", "Ganga"],
        "correct_index": 0,
    }
    music = os.path.join(BASE, "assets", "audio", "slot1_one_answer_left.mp3")
    out = render_video(q, "#4D96FF", os.path.join(BASE, "output_test.mp4"), os.path.join(BASE, "tmp_test"), bg_music=music, day=1, slot=1)
    print("Rendered:", out)
