"""
SEO Super Agent for GK Snippets Pipeline
-----------------------------------------
Features:
1. Performance Retrieval: Audits recent videos from YouTube Data API to analyze views and engagement.
2. Dynamic Topic Detection: Identifies subject matter (Ancient History, Modern History, Polity, Geography, Science, Economy, Art & Culture).
3. Metadata Improvisation:
   - High-CTR mobile Shorts title (< 70 chars, hook + topic + Day #Shorts)
   - Search-engine optimized description with exam target keywords & hashtags
   - 15-20 targeted YouTube tags
   - Optimized Instagram & Facebook captions
4. Robust Pre-filled Fallback: If YouTube API or network fails, uses a comprehensive keyword bank so the pipeline never breaks.
"""

import re
import html
import random
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── TOPIC KEYWORD MAPPING & FALLBACK SEO MATRIX ───────────────────────────────

TOPIC_RULES = [
    (
        "Ancient Indian History",
        r"(harappa|indus valley|burzahom|dholavira|vedic|rigveda|samaveda|ashoka|maurya|gupta|samudragupta|buddhism|jainism|pit-dwelling|megalith|chola|sangam)",
        [
            "Ancient Indian History", "Indus Valley Civilization", "Vedic Period", "UPSC Ancient History",
            "SSC History GK", "Samudragupta", "Harappan Sites", "Ancient India MCQs"
        ],
        ["#ancienthistory", "#indusvalley", "#historygk", "#upschistory", "#sschistory"]
    ),
    (
        "Medieval Indian History",
        r"(delhi sultanate|balban|alauddin|mughal|akbar|babur|aurangzeb|maratha|shivaji|vijayanagar|mansabdari|qutub|khilji|lodhi)",
        [
            "Medieval Indian History", "Mughal Empire GK", "Delhi Sultanate", "SSC CGL History",
            "UPSC Medieval History", "Indian History Quiz", "Balban", "History Facts"
        ],
        ["#medievalhistory", "#mughalempire", "#delhisultanate", "#historyquiz", "#upscprelims"]
    ),
    (
        "Modern Indian History & Freedom Struggle",
        r"(british|east india company|1857|congress|gandhi|nehru|bhagat singh|subhas chandra|viceroy|governor general|swadeshi|quit india|satyagraha|partition)",
        [
            "Modern Indian History", "Indian Freedom Struggle", "1857 Revolt", "Gandhian Era",
            "Governor General MCQs", "SSC CGL GK", "UPSC Modern History", "History Trivia"
        ],
        ["#modernhistory", "#freedomstruggle", "#indianhistory", "#gandhi", "#historyfacts"]
    ),
    (
        "Indian Polity & Constitution",
        r"(constitution|article|amendment|fundamental right|preamble|parliament|lok sabha|rajya sabha|president|prime minister|supreme court|high court|panchayat|election commission)",
        [
            "Indian Polity GK", "Constitution of India", "Articles and Amendments", "UPSC Polity",
            "SSC CGL Polity", "Fundamental Rights", "Indian Constitution Quiz", "Polity MCQs"
        ],
        ["#indianpolity", "#constitutionofindia", "#politygk", "#upscpolity", "#sscpolity"]
    ),
    (
        "Geography & Environment",
        r"(river|mountain|himalaya|plateau|soil|monsoon|national park|wildlife|cyclone|western ghats|delta|gulf|tributary|climate|forest|biosphere)",
        [
            "Indian Geography", "Rivers of India", "Physical Geography", "National Parks GK",
            "UPSC Geography", "SSC Geography", "Geography MCQs", "World Geography"
        ],
        ["#geographygk", "#indiangeography", "#physicalgeography", "#geographyquiz", "#upscgeography"]
    ),
    (
        "General Science & Everyday Tech",
        r"(physics|chemistry|biology|acid|base|vitamin|disease|cell|dna|gravity|newton|isro|planet|solar system|hormone|enzyme|blood|element|periodic table)",
        [
            "General Science GK", "Everyday Science", "Biology MCQs", "Chemistry GK",
            "Physics Quiz", "SSC General Science", "Science Trivia", "Human Body Facts"
        ],
        ["#generalscience", "#sciencegk", "#sciencequiz", "#biologygk", "#sciencetrivia"]
    ),
    (
        "Economics & Banking",
        r"(rbi|bank|inflation|gdp|budget|fiscal|monetary|niti aayog|five year plan|repo rate|tax|gst|sebi|stock market|census)",
        [
            "Indian Economy GK", "Banking Awareness", "RBI and Monetary Policy", "UPSC Economics",
            "SSC CGL Economics", "Indian Budget", "Economy MCQs", "Finance GK"
        ],
        ["#indianeconomy", "#bankinggk", "#economicsquiz", "#upsceconomy", "#budget2026"]
    ),
    (
        "Art, Culture & Literature",
        r"(dance|music|ghat|temple|sculpture|gandhara|mathura|painting|classical dance|unesco|festival|folk|monument|author|book)",
        [
            "Indian Art and Culture", "Classical Dances of India", "UNESCO World Heritage",
            "Ancient Indian Architecture", "Temple Architecture", "UPSC Art and Culture", "Culture GK"
        ],
        ["#artandculture", "#indianheritage", "#unescoworldheritage", "#culturequiz", "#upscculture"]
    )
]

# Baseline high-volume universal tags
UNIVERSAL_TAGS = [
    "GK Snippets", "General Knowledge", "GK Quiz", "Daily GK",
    "SSC CGL 2026", "UPSC Prelims", "Competitive Exam GK",
    "Shorts", "YouTube Shorts", "Quiz Time", "Study Motivation", "Exam Prep"
]

UNIVERSAL_HASHTAGS = [
    "#Shorts", "#ShortsFeed", "#YouTubeShorts", "#GKQuiz", "#GeneralKnowledge",
    "#DailyGK", "#QuizTime", "#UPSC", "#SSCCGL", "#RRBNTPC", "#StudyMotivation"
]

HOOK_TEMPLATES = [
    ("{q}? 99% Fail This! ❌ #Shorts", 68),
    ("{q}? Can You Answer in 5s? 🧠 #Shorts", 68),
    ("{q}? Tricky Exam Question! 🎯 #Shorts", 68),
    ("{q}? Test Your Brain! ⚡ #Shorts", 68),
    ("{q}? Only 1% Know This! 🤯 #Shorts", 68)
]


def clean_question_for_title(q_text, fallback_topic="General Knowledge"):
    """Strip filler question words and numbered prompts to extract the core subject for high-impact titles."""
    parts = re.split(r'[:\?]?\s*(?:\(?1[\.\)]|Which of the statement|Choose the right|Which are those)', q_text, flags=re.IGNORECASE)
    main_part = parts[0].strip() if parts else q_text
    if not main_part or len(main_part) < 8:
        main_part = q_text

    q_clean = re.sub(
        r'^(Which (one )?(among |of )?the following (provisions was not made in the |statements? (is|are|was) (not )?(a feature of the |correct about |true about )?|pairs? (is|are) correctly matched\??|was not a reason for |is not true about |are |is |was )?(true about |correct about )?|'
        r'Who among the following|What is the|In which year|Where is the|'
        r'Consider the following (statements regarding |landmarks in |princely states of the |pairs:? )?|'
        r'Some of the following (place \(s\) has/have revealed )?)\s*',
        '', main_part, flags=re.IGNORECASE
    ).strip()

    if not q_clean or len(q_clean) < 5:
        q_clean = fallback_topic

    if q_clean and q_clean[0].islower():
        q_clean = q_clean[0].upper() + q_clean[1:]

    q_clean = re.sub(r'[\?।!:,]+$', '', q_clean).strip()
    q_clean = re.sub(r'\s+', ' ', q_clean)
    return q_clean


# ── PERFORMANCE AUDIT HELPER ──────────────────────────────────────────────────

def audit_recent_performance(yt_client, published_history=None):
    """
    Fetches stats of up to 5 recently published videos using YouTube Data API.
    Returns a summary dict with performance metrics.
    """
    if not yt_client or not published_history:
        return {"status": "skipped", "message": "No client or history provided"}

    recent_items = [h for h in published_history if h.get("yt_id")]
    if not recent_items:
        return {"status": "no_history", "message": "No YouTube video IDs in history yet"}

    recent_ids = [h["yt_id"] for h in recent_items[-5:]]
    try:
        req = yt_client.videos().list(part="snippet,statistics", id=",".join(recent_ids))
        resp = req.execute()
        items = resp.get("items", [])

        summary = []
        for item in items:
            vid = item["id"]
            title = item["snippet"].get("title", "")
            stats = item.get("statistics", {})
            views = int(stats.get("viewCount", 0))
            likes = int(stats.get("likeCount", 0))
            comments = int(stats.get("commentCount", 0))
            summary.append({
                "video_id": vid,
                "title": title,
                "views": views,
                "likes": likes,
                "comments": comments
            })

        print(f"[SEO Agent] Performance Audit of {len(summary)} Recent Shorts:")
        for s in summary:
            print(f"  • {s['video_id']}: {s['views']} views, {s['likes']} likes | {s['title'][:40]}...")

        return {
            "status": "success",
            "count": len(summary),
            "summary": summary
        }
    except Exception as e:
        print(f"[SEO Agent] Warning: Could not retrieve YouTube video statistics: {e}")
        return {"status": "error", "error": str(e)}


# ── TOPIC DETECTION ───────────────────────────────────────────────────────────

def detect_topic(question_text):
    """
    Classifies a question into a GK topic based on keyword pattern matching.
    """
    q_lower = question_text.lower()
    for topic_name, pattern, topic_tags, topic_hashtags in TOPIC_RULES:
        if re.search(pattern, q_lower, re.IGNORECASE):
            return topic_name, topic_tags, topic_hashtags
    
    # Default fallback topic
    return (
        "General Knowledge",
        ["General Knowledge Quiz", "Important GK Questions", "Daily GK Practice"],
        ["#generalknowledge", "#gkquestions", "#dailyquiz"]
    )


# ── SEO METADATA GENERATOR ───────────────────────────────────────────────────

def generate_seo(q, day, slot, videos_per_day=2, yt_client=None, published_history=None):
    """
    Improvises YouTube, Instagram, Facebook, and Telegram SEO metadata for question `q`.
    Includes robust fallback mechanism if YouTube API audit fails.
    """
    # 1. Audit recent performance (non-blocking)
    audit = {}
    if yt_client and published_history:
        audit = audit_recent_performance(yt_client, published_history)

    # 2. Detect Question Topic
    question_text = q.get("question", "")
    topic_name, topic_tags, topic_hashtags = detect_topic(question_text)

    options = q.get("options", [])
    short_topic = topic_name.replace(" & Everyday Tech", "").replace(" & Freedom Struggle", "").replace(" & Constitution", "")
    q_clean = clean_question_for_title(question_text, fallback_topic=short_topic)

    # ── 1. QUESTION-FIRST VIRAL TITLE (< 68 chars strictly with #Shorts) ───
    # Pick a rotating hook template deterministically
    hook_idx = (day * 2 + slot) % len(HOOK_TEMPLATES)
    ordered_hooks = HOOK_TEMPLATES[hook_idx:] + HOOK_TEMPLATES[:hook_idx]

    title = None
    for tpl, max_len in ordered_hooks:
        cand = tpl.format(q=q_clean)
        if len(cand) <= max_len:
            title = cand
            break

    if not title:
        # Try compact fallback hook first
        compact_title = f"{q_clean}? 99% Fail! ❌ #Shorts"
        if len(compact_title) <= 68:
            title = compact_title
        else:
            # If still over 68 chars, trim cleanly at word boundary (~45 chars)
            words = q_clean.split()
            shortened = ""
            for w in words:
                if len(shortened + " " + w) > 45:
                    break
                shortened = (shortened + " " + w).strip()
            title = f"{shortened}? 99% Fail! ❌ #Shorts"

    # ── 2. HIGH-ENGAGEMENT DESCRIPTION WITH TIMESTAMPS & OPTIONS ──────────
    options_str = " | ".join([f"({chr(65+i)}) {opt}" for i, opt in enumerate(options)]) if options else "Drop your answer below!"
    all_hashtags = list(dict.fromkeys(UNIVERSAL_HASHTAGS[:6] + topic_hashtags + UNIVERSAL_HASHTAGS[6:]))
    hashtag_str = " ".join(all_hashtags[:12])

    description = (
        f"❓ {question_text}\n"
        f"👉 Drop your answer in the comments: {options_str}\n\n"
        f"🎯 100 Days of GK Snippets • Day {day:02d} (Part {slot}/{videos_per_day})\n"
        f"📚 Topic: {topic_name}\n\n"
        f"⏱️ Video Timeline:\n"
        f"00:00 🎯 Question Challenge\n"
        f"00:05 ⏳ 10s Timer Challenge (Countdown)\n"
        f"00:15 🎉 Correct Answer & Explanation\n\n"
        f"🏆 Target Exams:\n"
        f"UPSC CSE | SSC CGL 2026 | RRB NTPC | CDS | NDA | State PSCs | Bank PO | All Competitive Exams\n\n"
        f"🔍 Top Search Keywords:\n"
        f"• {topic_name} Important MCQs\n"
        f"• GK Questions 2026 for Competitive Exams\n"
        f"• General Knowledge Quiz with Answers\n"
        f"• Daily GK Practice by GK Snippets\n\n"
        f"🎁 SUNDAY GIVEAWAY: Like, Subscribe & Comment your answer daily to win exclusive study materials!\n"
        f"📄 Join our Telegram Channel for daily PDF notes & quiz alerts: @GK_Snippets\n\n"
        f"{hashtag_str}"
    )

    # ── 3. HIGH-VOLUME 20 TARGET TAGS (TOPIC + EXAMS + QUESTION) ───────────
    tags = list(dict.fromkeys(
        [q_clean[:30]] +
        topic_tags +
        UNIVERSAL_TAGS +
        ["UPSC Prelims 2026", "SSC CGL GK", "Daily Quiz", "Study IQ GK", "Khan Sir GK Style"]
    ))[:20]

    # ── 4. ENGAGING INSTAGRAM & FACEBOOK REELS CAPTIONS ───────────────────
    ig_caption = (
        f"🔥 {question_text}\n\n"
        f"👇 Drop your answer below: {options_str}\n"
        f"⏱️ Can you answer in 10 seconds?\n\n"
        f"🎯 Day {day:02d} • 100 Days of GK Snippets (Part {slot}/{videos_per_day})\n"
        f"🎁 Follow @GK_Snippets & comment daily to win the Sunday Study Gift!\n\n"
        f"{' '.join(all_hashtags[:15])}"
    )

    fb_caption = (
        f"🎯 100 Days of GK Snippets • Day {day:02d} (Part {slot}/{videos_per_day})\n\n"
        f"❓ {question_text}\n"
        f"👉 Options: {options_str}\n\n"
        f"👇 Watch the 18-second video to check if your answer is correct!\n"
        f"🎁 Comment below to enter the weekly giveaway.\n\n"
        f"{' '.join(all_hashtags[:10])}"
    )

    return {
        "topic": topic_name,
        "title": title,
        "description": description,
        "tags": tags,
        "ig_caption": ig_caption,
        "fb_caption": fb_caption,
        "audit": audit
    }


if __name__ == "__main__":
    # Self-test unit verification
    test_q = {
        "id": "q0005",
        "question": "Which of the following are true about Samudragupta? 1. He is also known as ‘Kaviraja’ 2. He is known as “Lichchhavi Dauhitra’ 3. He built most extensive empire after Asoka."
    }
    seo = generate_seo(test_q, day=3, slot=1, videos_per_day=2)
    print("Detected Topic:", seo["topic"])
    print("Generated Title:", seo["title"])
    print("Tags count:", len(seo["tags"]))
    print("Sample Tags:", seo["tags"][:5])
    print("Description Preview:\n", seo["description"][:200], "...")
