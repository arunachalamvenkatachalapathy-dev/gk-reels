import pymupdf, re, json, random

PDF_PATH = r"D:\downloads\1 downloaded\iso 14064\macas\Disha 1000 Mcq GS (sscstudy.com).pdf"
TARGET_JSON = r"C:\Users\NALINI ARUN\.gemini\antigravity\scratch\gk-reels\data\questions_en.json"

doc = pymupdf.open(PDF_PATH)
toc = doc.get_toc()

chapters = []
for item in toc:
    if item[0] == 2:
        chapters.append((item[1].strip(), item[2]))

def get_column_ordered_text(doc, start_p, end_p):
    text_chunks = []
    for p in range(start_p - 1, end_p):
        page = doc[p]
        blocks = page.get_text('blocks')
        valid = [b for b in blocks if 105 <= b[1] <= 750 and b[4].strip()]
        left = [b for b in valid if b[0] < 305]
        right = [b for b in valid if b[0] >= 305]
        left.sort(key=lambda b: b[1])
        right.sort(key=lambda b: b[1])
        for b in left + right:
            text_chunks.append(b[4])
    return '\n'.join(text_chunks)

def get_answer_key(doc, start_p, end_p):
    ans_map = {}
    for p in range(start_p - 1, end_p):
        t = doc[p].get_text()
        matches = re.findall(r'(?:^|\n)\s*(\d{1,3})\s*[\.:\)]?\s*\(([a-d])\)', t, re.IGNORECASE)
        for q_str, ans in matches:
            q_num = int(q_str)
            if q_num not in ans_map:
                ans_map[q_num] = ans.lower()
    return ans_map

def is_code_option(o):
    ol = o.lower()
    if re.search(r'\d+\s*(?:and|,|\&)', ol):
        return True
    if re.search(r'^\d+\s*only', ol) or re.search(r'\bonly\s*\d+', ol):
        return True
    if re.search(r'^[0-9,\s(i)(v)and\-\.]+$', ol):
        return True
    if re.search(r'^[a-d]\s*-\s*[a-d0-9]', ol):
        return True
    if re.search(r'\b(both 1|neither 1|only 1|only 2|only 3|only 4)\b', ol):
        return True
    return False

all_clean = []

for ch_idx, (ch_title, start_p) in enumerate(chapters):
    end_p = chapters[ch_idx+1][1] if ch_idx + 1 < len(chapters) else len(doc)
    ans_map = get_answer_key(doc, start_p, end_p)
    if not ans_map:
        continue
        
    split_p = end_p
    for p in range(start_p - 1, end_p):
        t = doc[p].get_text()
        if 'ANSWER KEY' in t or 'Hints & Solutions' in t or 'HINTS & SOLUTIONS' in t:
            split_p = p
            break
            
    ch_text = get_column_ordered_text(doc, start_p, split_p + 1)
    
    q_matches = list(re.finditer(r'(?:^|\n)\s*(\d{1,3})\.\s+(.*?)(?=\n\s*\d{1,3}\.|\Z)', ch_text, re.DOTALL))
    for qm in q_matches:
        q_num = int(qm.group(1))
        body = qm.group(2)
        
        m_opt = re.search(r'\([aA]\)\s*(.*?)\s*\([bB]\)\s*(.*?)\s*\([cC]\)\s*(.*?)\s*\([dD]\)\s*(.*)', body, re.DOTALL)
        if not m_opt:
            continue
            
        raw_q = body[:m_opt.start()].strip()
        q_text = ' '.join(raw_q.split())
        
        opt_a = ' '.join(m_opt.group(1).strip().split())
        opt_b = ' '.join(m_opt.group(2).strip().split())
        opt_c = ' '.join(m_opt.group(3).strip().split())
        
        raw_d = m_opt.group(4).strip()
        lines_d = [l.strip() for l in raw_d.splitlines() if l.strip() and not re.match(r'^\d+\.', l.strip()) and 'ANSWER' not in l.upper() and 'HINTS' not in l.upper() and 'https://' not in l]
        opt_d = ' '.join(' '.join(lines_d).split())
        
        opts = [opt_a, opt_b, opt_c, opt_d]
        
        bad_words = [
            'match list', 'assertion', 'reason (r)', 'codes:', 'statement', 'arrange the',
            'list-i', 'list i', 'column i', 'code:', 'which of the following pairs',
            'consider the following', 'select the correct answer using', 'indicate your answer',
            'which of the above', 'which among the following statements', 'correct chronological',
            'which are those sites', 'choose the right', 'choose the correct',
            'figure', 'diagram', 'given map', 'shown in the map', 'marked as', 'in the map',
            'following map'
        ]
        if any(bw in q_text.lower() for bw in bad_words):
            continue
            
        def clean_hf(t):
            t = re.sub(r'\s*[A-G]-\d+\s*\|\|.*', '', t)
            t = re.sub(r'\s*\|\|.*', '', t)
            t = re.sub(r'\s*https?://\S+', '', t)
            t = re.sub(r'\s*(?:Economics|Geography|History|General Science|Current Affairs|Indian Polity)\s*\|\|.*', '', t, flags=re.IGNORECASE)
            t = re.sub(r'[\uf800-\uf8ff]', '', t)
            return ' '.join(t.split())

        q_text = clean_hf(q_text)
        opts = [clean_hf(o) for o in opts]
            
        if any(is_code_option(o) for o in opts):
            continue
            
        if q_num not in ans_map:
            continue
        ans_char = ans_map[q_num]
        ans_idx = {'a': 0, 'b': 1, 'c': 2, 'd': 3}.get(ans_char)
        if ans_idx is None:
            continue
            
        if not (22 <= len(q_text) <= 135 and all(1 <= len(o) <= 52 for o in opts)):
            continue
            
        if not q_text or not q_text[0].isupper():
            continue
            
        if q_text.startswith(('Shortugai', 'Pig', 'Kalibangan', 'Bhogavo', 'Which of the following is correct', 'Among oil seeds')):
            continue
            
        # Punctuation normalization
        if not q_text.endswith(('?', ':', '.')):
            q_text += ':'
            
        all_clean.append({
            'chapter': ch_title,
            'q_num': q_num,
            'question': q_text,
            'options': opts,
            'correct_index': ans_idx,
            'ans_char': ans_char
        })

print(f"Total valid MCQs extracted: {len(all_clean)}")

# Let's inspect existing questions_en.json
with open(TARGET_JSON, 'r', encoding='utf-8') as f:
    old_data = json.load(f)

# Keep first 12 questions (indices 0 to 11) for continuity
preserved_qs = old_data[:12]
for q in preserved_qs:
    q['used'] = True

# Shuffle remaining extracted questions with a stable seed so diversity is high
random.seed(42)
random.shuffle(all_clean)

# Deduplicate with preserved questions
seen_q_texts = set(q['question'].lower() for q in preserved_qs)
final_pool = list(preserved_qs)

for q in all_clean:
    q_lower = q['question'].lower()
    if q_lower in seen_q_texts:
        continue
    seen_q_texts.add(q_lower)
    final_pool.append({
        'id': f"q{len(final_pool):04d}",
        'question': q['question'],
        'options': q['options'],
        'correct_index': q['correct_index'],
        'used': False
    })

print(f"Final combined pool size: {len(final_pool)}")
print(f"Preserved past published: {len(preserved_qs)} (q0000 - q0011)")
print(f"New clean upcoming questions: {len(final_pool) - len(preserved_qs)} (q0012 - q{len(final_pool)-1:04d})")

# Save backup of old questions_en.json first
with open(TARGET_JSON + ".bak", "w", encoding="utf-8") as f:
    json.dump(old_data, f, indent=2, ensure_ascii=False)

# Write updated clean questions_en.json
with open(TARGET_JSON, "w", encoding="utf-8") as f:
    json.dump(final_pool, f, indent=2, ensure_ascii=False)

print("Successfully wrote updated questions_en.json!")
