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

MONTHS = {"january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"}
STOPWORDS = {"which", "what", "who", "where", "when", "the", "some", "consider", "indian", "union", "following", "while", "in", "on", "at", "from", "since", "under", "after", "before", "a", "an"}


def extract_core_entity(q_text, topic="General Knowledge"):
    """
    Extracts the key conceptual entity or proper noun phrase from a competitive exam question.
    Prevents truncated sentence fragments or cutting off mid-clause.
    """
    # 1. Quoted terms (often the exact concept or moniker tested)
    quotes = re.findall(r"[\'\‘\“\"]([^\'\’\”\"]{3,35})[\'\’\”\"]", q_text)
    if quotes:
        valid_q = [q.strip() for q in quotes if len(q.strip()) > 3 and not re.match(r"^[a-d1-4]$", q.strip(), re.I)]
        if valid_q:
            return valid_q[0]

    clean = q_text.strip()

    # Remove introductory date/time clauses e.g. "In December 2013, ..."
    clean = re.sub(r'^(In|On|During)\s+[A-Za-z]+\s+\d{4},\s*', '', clean, flags=re.I)

    # Remove introductory conditional clauses e.g. "If a new state of the Indian Union is to be created, ..."
    if clean.lower().startswith("if ") and "," in clean:
        cond_part, rest = clean.split(",", 1)
        if any(term in cond_part.lower() for term in ["created", "suppose", "assumed", "given"]):
            clean = rest.strip()

    # Clean preambles and numbered clauses
    clean = re.sub(
        r"^(Which (one )?(among |of )?(the )?following\s*(provisions was not made in the |committees recommended the |statements? (is|are|was) (not )?(a feature of the |correct about |true about )?|pairs? (is|are) correctly matched\??|was not a reason for |is not true about |are |is |was |(places? \(s\) )?has/have revealed )?|Who among the following|What is the|In which year|Where is the|Consider the following (statements regarding |landmarks in |princely states of the |pairs:? )?|Some of the following)\s*",
        "", clean, flags=re.I
    ).strip()
    clean = re.split(r"[:\?]?\s*(?:\(?1[\.\)]|Which of the statement|Choose the right|Which are those)", clean)[0].strip()

    # Remove subordinating leading clauses (e.g. "While tinning of brass utensils, ...")
    if clean.lower().startswith("while ") and "," in clean:
        clean = clean.split(",", 1)[1].strip()
    if clean.lower().startswith("when ") and "," in clean:
        clean = clean.split(",", 1)[1].strip()

    # Look for capitalized sequences and proper noun phrases (e.g. Cartagena Protocol, Schedules of the Constitution)
    caps = re.findall(r"\b[A-Z][a-zA-Z0-9\-]*(?:\s+(?:of|the|and|in|for|on|de)\s+[A-Z][a-zA-Z0-9\-]*|\s+[A-Z][a-zA-Z0-9\-]*)+\b", clean)
    caps_filtered = []
    for c in caps:
        c_clean = re.sub(r"\s+(of|in|the|regarding|about|is|are|and|to|for|was|were|have|has|had|with|by|from)\s*$", "", c, flags=re.I).strip()
        words = c_clean.split()
        if not all(w.lower() in STOPWORDS or w.lower() in MONTHS for w in words):
            while words and (words[0].lower() in STOPWORDS or words[0].lower() in MONTHS):
                words.pop(0)
            if words:
                cand = " ".join(words)
                cand = re.sub(r"\s+(of|in|the|regarding|about|is|are|and|to|for|was|were|have|has|had|with|by|from)\s*$", "", cand, flags=re.I).strip()
                if len(cand) >= 5:
                    caps_filtered.append(cand)
    if caps_filtered:
        best_cap = max(caps_filtered, key=len)
        if len(best_cap) >= 6:
            return best_cap

    # Look for key noun phrases after verbs/prepositions
    np_match = re.search(r'\b(market capitalization|nuclear reactor|rings of Saturn|supply-side economics|ammonium chloride|biosafety|national income|first sovereign real ruler|research station|antarctica)\b', clean, re.I)
    if np_match:
        return np_match.group(0).strip().title()

    # Meaningful clause extraction up to 35 characters
    words = clean.split()
    cand = ""
    for w in words:
        if len(cand + " " + w) > 35:
            break
        cand = (cand + " " + w).strip()

    # Clean trailing prepositions/auxiliary verbs in a loop to prevent hanging words
    while re.search(r"\s+(of|in|the|regarding|about|is|are|and|to|for|was|were|have|has|had|with|by|from|must|should|can|could|would|will|shall|may|might)\s*$", cand, flags=re.I):
        cand = re.sub(r"\s+(of|in|the|regarding|about|is|are|and|to|for|was|were|have|has|had|with|by|from|must|should|can|could|would|will|shall|may|might)\s*$", "", cand, flags=re.I).strip()

    cand = re.sub(r'[\?।!:,]+$', '', cand).strip()
    if len(cand) >= 6 and cand.lower() not in ["indian companies", "while tinning", "the credit"]:
        return cand.title()

    return topic


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


def format_smart_title_en(q, day, slot, topic_name):
    """
    Rotates deterministically across 8 high-reach archetypes.
    Guarantees title <= 68 characters, contains #Shorts, and front-loads key entities.
    """
    short_topic = topic_name.replace(" & Everyday Tech", "").replace(" & Freedom Struggle", "").replace(" & Constitution", "")
    q_text = q.get("question", "").strip()
    entity = extract_core_entity(q_text, topic=short_topic)

    direct_q = re.sub(r'[:\?]+$', '', q_text).strip()
    direct_q = re.sub(r'^(In which year|Where is|What is|Who was|Who is|What are)\s+', r'\g<0> ', direct_q, flags=re.I)
    is_direct_usable = len(direct_q) <= 50 and ("?" in q_text or re.match(r'^(what|who|where|when|why|how|which)\b', q_text, re.I))

    templates = [
        f"{entity} | GK Questions and Answers #Shorts",
        f"{entity} | Important Exam GK Quiz #Shorts",
        f"{direct_q}? #Shorts" if is_direct_usable else f"{entity} Explained | UPSC & SSC GK #Shorts",
        f"{entity} MCQs | Can You Answer This? #Shorts",
        f"{entity} | {short_topic} GK Questions #Shorts",
        f"The Truth About {entity} | GK Facts #Shorts",
        f"{entity} | Top Repeated Exam MCQs #Shorts",
        f"{entity} Quiz | Test Your GK Score #Shorts",
    ]

    idx = (day * 3 + slot) % len(templates)
    title = templates[idx]
    if len(title) > 68:
        title = f"{entity} | GK Quiz #Shorts"
        if len(title) > 68:
            title = f"{short_topic} GK Questions #Shorts"

    return title, entity


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

    # 2. Detect Question Topic & Format Smart Title
    question_text = q.get("question", "")
    topic_name, topic_tags, topic_hashtags = detect_topic(question_text)
    options = q.get("options", [])

    title, entity = format_smart_title_en(q, day, slot, topic_name)

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
        [entity[:30]] +
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
