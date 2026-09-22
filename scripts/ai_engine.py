import os
import sys
import json
import requests
import re

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip().strip('"\'')
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip().strip('"\'')

OPENROUTER_MODELS = [
    "deepseek/deepseek-chat",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemini-2.0-flash-exp:free",
    "openai/gpt-4o-mini",
]


def call_openrouter(prompt, system_prompt="You are a viral YouTube Shorts and Instagram Reels algorithm expert."):
    if not OPENROUTER_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/arunachalamvenkatachalapathy-dev/gk-reels",
        "X-Title": "GK Reels Viral Engine"
    }

    for model in OPENROUTER_MODELS:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.4,
            "max_tokens": 800,
            "response_format": {"type": "json_object"}
        }
        try:
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=20)
            if resp.status_code == 200:
                res = resp.json()
                content = res["choices"][0]["message"]["content"]
                return json.loads(content)
            else:
                print(f"[AI Engine] Model {model} returned HTTP {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            print(f"[AI Engine] Error with model {model}: {e}")
            continue

    return None


def call_gemini_fallback(prompt):
    if not GEMINI_API_KEY:
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        resp = requests.post(
            url,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.3
                }
            },
            timeout=20
        )
        if resp.status_code == 200:
            data = resp.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(raw_text)
    except Exception as ge:
        print(f"[AI Engine] Gemini fallback error: {ge}")
    return None


def generate_viral_package(q, day, slot, language="English"):
    q_text = q.get("question", "").strip()
    opts = q.get("options", [])
    correct_idx = q.get("correct_index", 0)
    correct_opt = opts[correct_idx] if opts and correct_idx < len(opts) else ""

    if language.lower() == "hindi":
        prompt = f"""You are a master of viral Indian educational YouTube Shorts and Reels (targeting SSC, Railway, UP Police, and KBC fans).
Analyze this Hindi GK question:
Question: "{q_text}"
Options: {opts}
Correct Answer: "{correct_opt}"

Generate a viral metadata package that hooks the viewer in the first 1.5 seconds, drives comments, and forces video loops.
Output ONLY a JSON object with these exact keys:
{{
  "viral_hook": "A short, addictive 1-sentence hook in Hindi to show at the top of the video or voiceover (e.g., '99% लोग गलत जवाब देते हैं! क्या आप जानते हैं?')",
  "title": "High-CTR YouTube Shorts Title in Hindi with emoji and #shorts (< 65 chars, provocative/curiosity)",
  "badge_text": "Ultra-short 3-4 word punchy badge for top of video (e.g. '🔥 99% लोग फेल!', '⚡ 5-सेकंड टेस्ट', '🎯 KBC स्पेशल')",
  "tags": ["15-20 viral Hindi GK exam tags like 'gk in hindi', 'samanya gyan', 'gk quiz', etc."],
  "pinned_comment": "An irresistible bonus trivia question in Hindi with 'Comment your answer below 👇' to trigger 100+ comments",
  "short_fact": "A punchy 1-sentence interesting explanation of why the answer is correct"
}}"""
    else:
        prompt = f"""You are an elite YouTube Shorts algorithm engineer specializing in high-retention trivia and educational shorts.
Analyze this General Knowledge MCQ:
Question: "{q_text}"
Options: {opts}
Correct Answer: "{correct_opt}"

Generate a viral metadata package that stops users from swiping away in the first 1.5 seconds, maximizes Viewed vs Swiped Away (VVSA > 75%), and triggers comment debate.
Output ONLY a JSON object with these exact keys:
{{
  "viral_hook": "An addictive 1-sentence curiosity hook (e.g., '99% of graduates get this basic question WRONG! Can you solve it in 5s?')",
  "title": "High-CTR mobile Shorts Title with emoji and #Shorts (< 65 chars, curiosity-driven)",
  "badge_text": "Ultra-short 3-4 word punchy badge for top of video (e.g. '🔥 90% FAIL THIS', '⚡ 5-SEC BRAIN TEST', '🎯 UPSC TRIVIA')",
  "tags": ["15-20 high-volume search tags like 'GK Quiz', 'General Knowledge', 'Trivia', 'Shorts', etc."],
  "pinned_comment": "An irresistible challenge comment ending with: Like & Subscribe, then comment 'GUIDE' below for free revision notes! 📚👇",
  "short_fact": "A punchy 1-sentence fascinating fact explaining the correct answer"
}}"""

    # 1. Try OpenRouter first
    res = call_openrouter(prompt)
    if res and res.get("title") and res.get("viral_hook"):
        print(f"[AI Engine] Generated viral package via OpenRouter for {q.get('id')}")
        return res

    # 2. Try Gemini fallback
    res = call_gemini_fallback(prompt)
    if res and res.get("title") and res.get("viral_hook"):
        print(f"[AI Engine] Generated viral package via Gemini for {q.get('id')}")
        return res

    # 3. Rule-based fallback
    print(f"[AI Engine] Using rule-based viral fallback for {q.get('id')}")
    if language.lower() == "hindi":
        return {
            "viral_hook": "99% लोग इस सवाल का गलत जवाब देते हैं! क्या आप जानते हैं?",
            "title": f"{q_text[:45]} | GK Quiz Hindi #shorts",
            "badge_text": "🔥 99% लोग फेल!",
            "tags": ["gk in hindi", "samanya gyan", "gk quiz", "shorts", "daily gk"],
            "pinned_comment": "क्या आपने सही उत्तर दिया? वीडियो लाइक और सब्सक्राइब करें, फिर फ्री नोट्स के लिए नीचे 'GUIDE' कमेंट करें! 📚👇",
            "short_fact": f"सही उत्तर '{correct_opt}' है।"
        }
    else:
        return {
            "viral_hook": "90% of people fail this quick quiz! Can you answer in 5 seconds?",
            "title": f"{q_text[:45]} 🎯 Daily GK Quiz #Shorts",
            "badge_text": "🔥 90% FAIL THIS",
            "tags": ["gk quiz", "general knowledge", "trivia", "shorts", "upsc gk"],
            "pinned_comment": "Did you get it right? Like & Subscribe, then comment 'GUIDE' below for free revision notes! 📚👇",
            "short_fact": f"The correct answer is {correct_opt}."
        }
