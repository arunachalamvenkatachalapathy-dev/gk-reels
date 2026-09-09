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
    "#gksnippets", "#gkquiz", "#generalknowledge", "#currentaffairs",
    "#dailygk", "#shorts", "#reels", "#quiz", "#upsc", "#ssccgl"
]

HOOK_TEMPLATES = [
    "90% Fail This {topic} Question! 🎯",
    "Can You Answer in 5 Seconds? 🧠 {topic}",
    "Test Your Memory! ⚡ {topic} Quiz",
    "Tricky Exam Question! 🏛️ {topic}",
    "Only 5% Get All 4 Right! 🔥 {topic}"
]


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

    # 3. Formulate High-CTR Title (< 70 chars for mobile Shorts feed)
    hook_tpl = random.choice(HOOK_TEMPLATES)
    short_topic = topic_name.replace(" & Everyday Tech", "").replace(" & Freedom Struggle", "").replace(" & Constitution", "")
    title_hook = hook_tpl.format(topic=short_topic)

    title_candidate = f"{title_hook} • Day {day:02d} #Shorts"
    if len(title_candidate) > 70:
        title_candidate = f"Day {day:02d} Quiz: {short_topic} 🎯 #Shorts"
    if len(title_candidate) > 70:
        title_candidate = f"Day {day:02d} | 100 Days of GK Snippets 🎯 #Shorts"

    title = title_candidate

    # 4. Formulate Rich Search-Optimized Description
    all_hashtags = list(dict.fromkeys(topic_hashtags + UNIVERSAL_HASHTAGS))
    hashtag_string = " ".join(all_hashtags[:12])

    description = (
        f"🎯 Day {day:02d} (Part {slot}/{videos_per_day}) | 100 Days of GK Snippets\n\n"
        f"❓ {question_text}\n\n"
        f"⏱️ Test your speed! Drop your answer in the comments before the 10-second countdown ends.\n\n"
        f"📚 Topic: {topic_name}\n"
        f"🎯 Target Exams: UPSC CSE, SSC CGL 2026, RRB NTPC, State PSCs, NDA, CDS, Banking & AFCAT.\n\n"
        f"🎁 SUNDAY GIVEAWAY: Like, Subscribe & Comment your answer daily to win exclusive study materials!\n"
        f"📲 Join our Telegram Channel for daily PDF notes & quiz alerts: @GK_Snippets\n\n"
        f"{hashtag_string}\n\n"
        f"#Shorts"
    )

    # 5. Formulate 15-20 Target Tags for YouTube Video Snippet
    tags = list(dict.fromkeys(topic_tags + UNIVERSAL_TAGS))[:20]

    # 6. Instagram & Facebook Optimized Captions
    ig_caption = (
        f"✨ Day {day:02d} | 100 Days of GK Snippets (Part {slot}/{videos_per_day})\n\n"
        f"❓ {question_text}\n\n"
        f"👇 Comment your answer (A, B, C, or D) below!\n"
        f"🎁 Follow @GK_Snippets & share with a study buddy to win the Sunday Study Gift!\n\n"
        f"{' '.join(all_hashtags[:15])}"
    )

    fb_caption = (
        f"🎯 100 Days of GK Snippets • Day {day:02d} (Part {slot}/{videos_per_day})\n\n"
        f"❓ {question_text}\n\n"
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
