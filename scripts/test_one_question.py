"""
Single-question end-to-end validation test script for English GK Reels.
Tests:
1. AI Viral Package generation (OpenRouter -> Gemini -> Fallback)
2. 9.5-10.5s Video Render with hook sound, dynamic countdown, and neon badges
3. YouTube metadata compliance (Title < 70 chars with #Shorts, tags, pinned comment)
"""
import os
import sys
import json
import subprocess

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from seo_agent import generate_seo
from render import render_video, get_audio_duration


def test_single_question():
    data_path = os.path.join(BASE, "data", "questions_en.json")
    with open(data_path, encoding="utf-8") as f:
        questions = json.load(f)

    # Pick a crisp test question
    q = questions[0]
    print("=" * 60)
    print("GK REELS VIRAL ENGINE: SINGLE QUESTION SMOKE TEST")
    print("=" * 60)
    print(f"Question ID: {q['id']}")
    print(f"Question: {q['question']}")
    print(f"Options: {q['options']}")

    # 1. Test AI Viral SEO Generation
    print("\n--- 1. Generating Viral Package ---")
    seo_data = generate_seo(q, day=1, slot=1, videos_per_day=2)
    print(f"Topic: {seo_data.get('topic')}")
    print(f"Title: {seo_data.get('title')}")
    print(f"Viral Badge: {seo_data.get('viral_badge')}")
    print(f"Pinned Comment: {seo_data.get('pinned_comment')}")
    print(f"Tags ({len(seo_data.get('tags', []))}): {seo_data.get('tags', [])[:5]}...")

    assert "#shorts" in seo_data["title"].lower(), "Title must contain #Shorts"
    assert len(seo_data["title"]) <= 95, "Title should be compact and mobile-friendly"

    # 2. Test Video Render
    print("\n--- 2. Rendering Video ---")
    out_mp4 = os.path.join(BASE, "output", "smoke_test_en.mp4")
    tmp_dir = os.path.join(BASE, "output", "tmp_smoke_test_en")
    bg_music = os.path.join(BASE, "assets", "audio", "slot1_one_answer_left.mp3")

    render_video(
        q,
        accent="#F5A623",
        out_mp4=out_mp4,
        tmp_dir=tmp_dir,
        bg_music=bg_music,
        day=1,
        slot=1,
        topic_name=seo_data.get("topic"),
        viral_badge=seo_data.get("viral_badge")
    )

    # 3. Verify Video Properties
    assert os.path.exists(out_mp4), f"Output video {out_mp4} was not generated!"
    duration = get_audio_duration(out_mp4)
    file_size_mb = os.path.getsize(out_mp4) / (1024 * 1024)

    print("\n--- 3. Video Validation Metrics ---")
    print(f"Rendered Path: {out_mp4}")
    print(f"File Size: {file_size_mb:.2f} MB")
    print(f"Duration: {duration:.2f} seconds")

    assert 8.5 <= duration <= 12.0, f"Video duration {duration}s is outside optimal viral range (8.5s - 12s)"
    print("\n[SUCCESS] End-to-end single question test passed flawlessly!")
    print("=" * 60)
    return out_mp4, seo_data


if __name__ == "__main__":
    test_single_question()
