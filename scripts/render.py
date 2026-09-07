"""
Renders a single 15-second quiz video from a question dict.

Slide 1 (0-10s): question + 4 options, no answer shown.
Slide 2 (10-15s): same layout, correct option highlighted + ANSWER tag.

Pure HTML/CSS -> PNG screenshot via Playwright (no image-generation API,
so nothing here can fail on an external API outage). Audio is the
pre-generated tension bed (looped/trimmed to 10s) + a ding at the 10s mark.
"""
import os
import html
from playwright.sync_api import sync_playwright
import subprocess

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.path.join(BASE, "templates", "slide.html")
ASSETS = os.path.join(BASE, "assets")
TENSION = os.path.join(ASSETS, "tension_bed.mp3")
DING = os.path.join(ASSETS, "reveal_ding.mp3")

LETTERS = ["A", "B", "C", "D"]


def _esc(s):
    return html.escape(s, quote=False)


def build_html(question, options, correct_index, accent, show_answer):
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

    tpl = open(TEMPLATE_PATH, encoding="utf-8").read()
    tpl = tpl.replace("{{ACCENT}}", accent)
    tpl = tpl.replace("{{QUESTION}}", _esc(question))
    tpl = tpl.replace("{{OPTIONS}}", "\n".join(options_html))
    tpl = tpl.replace("{{ANSWER_TAG}}", answer_tag)
    return tpl


def screenshot_html(html_str, out_png, page):
    page.set_content(html_str, wait_until="load")
    page.screenshot(path=out_png)


def render_video(question_obj, accent, out_mp4, tmp_dir):
    os.makedirs(tmp_dir, exist_ok=True)
    slide1_png = os.path.join(tmp_dir, "slide1.png")
    slide2_png = os.path.join(tmp_dir, "slide2.png")

    html1 = build_html(question_obj["question"], question_obj["options"],
                        question_obj["correct_index"], accent, show_answer=False)
    html2 = build_html(question_obj["question"], question_obj["options"],
                        question_obj["correct_index"], accent, show_answer=True)

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

    # Build audio track: tension bed for 10s, ding right at 10s, silence-ish tail for 5s
    audio_track = os.path.join(tmp_dir, "audio_track.mp3")
    subprocess.run([
        "ffmpeg", "-y",
        "-i", TENSION,
        "-i", DING,
        "-filter_complex",
        "[1:a]adelay=10000|10000[ding];"
        "[0:a][ding]amix=inputs=2:duration=longest:dropout_transition=0[out]",
        "-t", "15",
        "-map", "[out]",
        audio_track,
    ], check=True)

    # Mux video + audio
    subprocess.run([
        "ffmpeg", "-y",
        "-i", video_only,
        "-i", audio_track,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
        out_mp4,
    ], check=True)

    return out_mp4


if __name__ == "__main__":
    import json, sys
    q = {
        "question": "Which river is known as the 'Sorrow of Bihar'?",
        "options": ["Kosi", "Gandak", "Son", "Ganga"],
        "correct_index": 0,
    }
    out = render_video(q, "#4D96FF", os.path.join(BASE, "output_test.mp4"), os.path.join(BASE, "tmp_test"))
    print("Rendered:", out)
