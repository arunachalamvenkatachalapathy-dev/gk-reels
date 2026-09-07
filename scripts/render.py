"""
Renders a single 15-second quiz video from a question dict.

Slide 1 (0-10s): question + 4 options, no answer shown.
Slide 2 (10-15s): same layout, correct option highlighted + ANSWER tag.

Audio:
  - 0.3s - 3.5s: Question read aloud via Edge-TTS (en-IN-PrabhatNeural).
  - 3.5s - 10.0s: Fast, high-energy countdown suspense beat.
  - 10.0s: Chime Ding sound effect when correct option turns green.
  - 10.2s - 13.5s: Full answer announced ("The correct answer is Option A: Kosi").
  - 13.5s - 15.0s: Outro fade.
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
TENSION = os.path.join(ASSETS, "audio", "fast_beat.mp3") if os.path.exists(os.path.join(ASSETS, "audio", "fast_beat.mp3")) else os.path.join(ASSETS, "tension_bed.mp3")
DING = os.path.join(ASSETS, "reveal_ding.mp3")

LETTERS = ["A", "B", "C", "D"]


def _esc(s):
    return html.escape(s, quote=False)


def build_html(question, options, correct_index, accent, show_answer, q_id="q0000"):
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

    tpl = open(TEMPLATE_PATH, encoding="utf-8").read()
    tpl = tpl.replace("{{ACCENT}}", accent)
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
    # Brisk, natural Indian male teacher voice
    voice = "en-IN-PrabhatNeural"
    
    # 1. Question voiceover
    comm_q = edge_tts.Communicate(question_text, voice, rate="+10%")
    await comm_q.save(q_voice_path)

    # 2. Answer voiceover (full option text)
    comm_ans = edge_tts.Communicate(answer_text, voice, rate="+16%")
    await comm_ans.save(ans_voice_path)


def render_video(question_obj, accent, out_mp4, tmp_dir, bg_music=None):
    os.makedirs(tmp_dir, exist_ok=True)
    slide1_png = os.path.join(tmp_dir, "slide1.png")
    slide2_png = os.path.join(tmp_dir, "slide2.png")

    q_id = question_obj.get("id", "q0000")
    html1 = build_html(question_obj["question"], question_obj["options"],
                        question_obj["correct_index"], accent, show_answer=False, q_id=q_id)
    html2 = build_html(question_obj["question"], question_obj["options"],
                        question_obj["correct_index"], accent, show_answer=True, q_id=q_id)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        screenshot_html(html1, slide1_png, page)
        screenshot_html(html2, slide2_png, page)
        browser.close()

    # Build the 15s silent video track: slide1 held 10s, slide2 held 5s
    video_only = os.path.join(tmp_dir, "video_only.mp4")
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1", "-t", "10", "-i", slide1_png,
        "-loop", "1", "-t", "5", "-i", slide2_png,
        "-filter_complex",
        "[0:v]fps=30,format=yuv420p[v0];[1:v]fps=30,format=yuv420p[v1];[v0][v1]concat=n=2:v=1:a=0[v]",
        "-map", "[v]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        video_only,
    ], check=True)

    # Generate voiceover for question and full answer
    correct_letter = LETTERS[question_obj["correct_index"]]
    correct_opt_text = question_obj["options"][question_obj["correct_index"]]
    
    # If option text is over 12 words, take first 10 words to fit 3.5s window
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

    # Pick background music track
    music_file = bg_music if (bg_music and os.path.exists(bg_music)) else TENSION

    if has_voice:
        # Mix: Background beat (ducked at 0.25) + Loud Voice (1.8) + Chime Ding (1.5)
        subprocess.run([
            "ffmpeg", "-y",
            "-i", video_only,
            "-ss", "2", "-i", music_file,
            "-i", q_voice_mp3,
            "-i", DING,
            "-i", ans_voice_mp3,
            "-filter_complex",
            "[1:a]atrim=0:15,atempo=1.2,afade=t=out:st=14:d=1,volume=0.25[bg];"
            "[2:a]adelay=300|300,volume=1.8[vq];"
            "[3:a]adelay=10000|10000,volume=1.5[ding];"
            "[4:a]adelay=10200|10200,volume=1.8[va];"
            "[bg][vq][ding][va]amix=inputs=4:duration=first:dropout_transition=0:normalize=0[out]",
            "-map", "0:v", "-map", "[out]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-t", "15",
            out_mp4,
        ], check=True)
    else:
        # Fallback music-only mix
        subprocess.run([
            "ffmpeg", "-y",
            "-i", video_only,
            "-t", "15", "-i", music_file,
            "-i", DING,
            "-filter_complex",
            "[1:a]atempo=1.2,afade=t=out:st=14:d=1,volume=0.85[music];"
            "[2:a]adelay=10000|10000,volume=1.4[ding];"
            "[music][ding]amix=inputs=2:duration=first:dropout_transition=0[out]",
            "-map", "0:v", "-map", "[out]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-t", "15",
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
    music = os.path.join(BASE, "assets", "audio", "fast_beat.mp3")
    out = render_video(q, "#4D96FF", os.path.join(BASE, "output_test.mp4"), os.path.join(BASE, "tmp_test"), bg_music=music)
    print("Rendered:", out)
