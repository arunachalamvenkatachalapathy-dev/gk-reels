"""Approval-gated quiz renderer: navy/gold, real countdown, checked payoff."""
import os, re, json, base64, asyncio, subprocess, urllib.request, urllib.error
from playwright.sync_api import sync_playwright
import edge_tts
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(BASE, "assets")
LETTERS = ["A", "B", "C", "D"]
def get_audio_duration(path):
    return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",path],text=True))

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



# ── Fish Audio Voice Config (English Channel) ────────────────────────────────
FISH_AUDIO_API_URL = "https://api.fish.audio/v1/tts"
# User's custom SRK voice model
FISH_VOICE_MODEL_ID = "f86d3a05bd004b3abb580698dedf2060"


def _fish_audio_tts(text: str, out_path: str, api_key: str, model_id: str) -> bool:
    """
    Call Fish Audio TTS API (S2.1 Pro engine) and save the MP3 to out_path.
    Returns True on success, False on any failure.
    S2.1 Pro is passed as HTTP header 'model: s2.1-pro'.
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
                "model": "s2.1-pro-free",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        if len(data) < 500:
            print(f"  [Fish Audio] Response too small ({len(data)} bytes), skipping.")
            return False
        with open(out_path, "wb") as f:
            f.write(data)
        print(f"  [Fish Audio S2.1 Pro] OK {os.path.basename(out_path)} ({len(data)//1024} KB)")
        return True
    except Exception as exc:
        print(f"  [Fish Audio] WARN Failed: {exc}")
        return False


async def _save_edge(text, voice, path):
    for attempt in range(3):
        try:
            await edge_tts.Communicate(text, voice, rate="+10%").save(path)
            return
        except Exception:
            if attempt == 2: raise
            await asyncio.sleep(1 + attempt)

async def generate_voiceover(question_text, answer_text, q_voice_path, ans_voice_path):
    """
    Generate voiceover MP3s for the English channel.
    Primary:  Fish Audio S2.1 Pro with user's SRK voice (f86d3a05...).
    Fallback: edge-tts en-IN-PrabhatNeural.
    """
    fish_api_key = os.environ.get("FISH_AUDIO_API_KEY", "")
    used_fish = False

    if fish_api_key:
        print("  [Fish Audio S2.1 Pro] Generating English voiceover...")
        ok_q = _fish_audio_tts(question_text, q_voice_path, fish_api_key, FISH_VOICE_MODEL_ID)
        ok_a = _fish_audio_tts(answer_text,   ans_voice_path, fish_api_key, FISH_VOICE_MODEL_ID)
        if ok_q and ok_a:
            used_fish = True

    if not used_fish:
        print("  [Edge-TTS] Falling back to en-IN-PrabhatNeural...")
        voice = "en-IN-PrabhatNeural"
        await _save_edge(question_text, voice, q_voice_path)
        await _save_edge(answer_text, voice, ans_voice_path)
        print("  [Edge-TTS] OK Voiceover generated.")


# Reviewed facts are editorial input, never an AI-generated explanation at render time.
# Unknown queue entries fail closed until an editor supplies a checked explanation.
LANG = 'en'
REVIEWED = {'q0075': {'speech_answer': 'Option A, Special Drawing Rights.', 'display_question': 'What does "paper gold" mean?', 'options': ['IMF Special Drawing Rights', 'World Bank loans', 'Gold-backed currencies', 'Deficit financing'], 'correct_index': 0, 'explanation': 'SDRs are reserve assets, not currency or physical gold.', 'source_url': 'https://www.imf.org/en/topics/special-drawing-right', 'source_label': 'Source: IMF | Special Drawing Rights', 'verified_topic': 'ECONOMY'}}

STYLE = '''
*{box-sizing:border-box}body{margin:0;width:1080px;height:1920px;background:#081427;color:#f5f6fa;font-family:"Noto Sans", "Noto Sans Devanagari",Arial,sans-serif}
main{position:absolute;left:72px;top:220px;width:824px;height:1240px}
header{display:flex;align-items:center;gap:18px;font-size:32px;color:#cbd5e1;letter-spacing:1px}header img{width:64px;height:64px;border-radius:16px}header b{color:#e7bd67}
.topic{margin-top:30px;font-size:28px;color:#e7bd67;letter-spacing:2px}.question{font-size:70px;line-height:1.25;font-weight:800;margin:20px 0 32px}
.options{display:grid;gap:18px}.option{min-height:118px;padding:20px 24px;display:flex;align-items:center;gap:22px;border-radius:20px;background:#12243c;border:2px solid #30435b;font-size:44px;line-height:1.2;font-weight:600}
.letter{display:flex;align-items:center;justify-content:center;flex-shrink:0;width:58px;height:58px;border-radius:13px;border:2px solid #e7bd67;color:#e7bd67;font-size:32px}.correct{background:#163e35;border:3px solid #59d997}.correct .letter{background:#59d997;border-color:#59d997;color:#081427}.dim{opacity:.48}
.beat{height:138px;margin-top:30px;display:flex;align-items:center;justify-content:space-between;border-top:2px solid #30435b}.beat-label{font-size:32px;color:#d8e0ea}.number{font-size:96px;line-height:1;color:#e7bd67;font-weight:800}
.explain{margin-top:28px;padding:26px 30px;background:#12243c;border-left:6px solid #59d997;border-radius:12px}.explain b{display:block;font-size:26px;color:#59d997;letter-spacing:2px;margin-bottom:12px}.explain p{font-size:39px;line-height:1.3;margin:0}.source{font-size:22px;color:#b7c6d8;margin-top:16px}
.follow{font-size:34px;color:#e7bd67;font-weight:700;margin-top:18px}.rule{position:absolute;left:72px;top:170px;width:824px;height:5px;background:#e7bd67}
'''


def prepare_content(q):
    content = dict(q)
    if q.get('id') in REVIEWED:
        content.update(REVIEWED[q['id']])
    if not content.get('explanation') or not content.get('source_url'):
        raise ValueError('Source-checked explanation required before rendering: ' + q.get('id', 'unknown'))
    if len(content['options']) != 4 or not 0 <= content['correct_index'] < 4:
        raise ValueError('Exactly four options and a valid answer index required')
    if len(content['explanation'].split()) > 24:
        raise ValueError('Explanation must be one short sentence (maximum 24 words)')
    content['question'] = content.get('display_question', content['question'])
    # Omit category unless editorially verified. Never infer from ambiguous keywords.
    content['topic'] = content.get('verified_topic', '')
    return content


def build_card(q, phase='question', number=None):
    import html
    esc = lambda s: html.escape(str(s), quote=True)
    logo = os.path.join(ASSETS, 'logo.jpg')
    logo_html = ''
    if os.path.isfile(logo):
        logo_html = '<img src="data:image/jpeg;base64,' + base64.b64encode(open(logo,'rb').read()).decode() + '">'
    is_answer = phase in ('reveal','explain')
    opts = []
    for i, opt in enumerate(q['options']):
        cls = 'correct' if is_answer and i == q['correct_index'] else ('dim' if is_answer else '')
        opts.append(f'<div class="option {cls}"><span class="letter">{LETTERS[i]}</span><span>{esc(opt)}</span></div>')
    hi = LANG == 'hi'
    label = ('सवाल सुनिए' if hi else 'Listen. Then choose.') if phase == 'question' else ('तीन सेकंड - अपना जवाब चुनिए' if hi else '3 seconds. Lock your answer.')
    if is_answer: label = 'सही जवाब' if hi else 'The answer'
    beat = f'<div class="beat"><span class="beat-label">{label}</span><span class="number">{esc(number) if number else (LETTERS[q["correct_index"]] if is_answer else "?")}</span></div>'
    explanation = ''
    if phase == 'explain':
        explanation = f'<section class="explain"><b>{"याद रखिए" if hi else "WHY IT MATTERS"}</b><p>{esc(q["explanation"])}</p><div class="source">{esc(q.get("source_label", "Checked source"))}</div></section><div class="follow">{"रोज़ एक सवाल, साथ में वजह।" if hi else "One exam trap every day. Follow."}</div>'
        beat = ''
    font_css = ''
    for face, filename in [('Noto Sans', '1-QuizSans.ttf'), ('Noto Sans Devanagari', '2-QuizHindi.ttf')]:
        path = os.path.join(ASSETS, 'fonts', filename)
        if not os.path.isfile(path): raise ValueError('Bundled font missing: ' + filename)
        encoded = base64.b64encode(open(path, 'rb').read()).decode()
        font_css += f'@font-face{{font-family:"{face}";src:url(data:font/ttf;base64,{encoded}) format("truetype");font-weight:400;}}'
    return f'<!doctype html><meta charset="utf-8"><style>{font_css}{STYLE}</style><div class="rule"></div><main><header>{logo_html}<b>GK SNIPPETS{" HINDI" if hi else ""}</b></header><div class="topic">{esc(q["topic"])}</div><div class="question">{esc(q["question"])}</div><div class="options">{"".join(opts)}</div>{beat}{explanation}</main>'


def timing_plan(q_duration, answer_duration, why_duration):
    if min(q_duration, answer_duration, why_duration) <= 0:
        raise ValueError('All speech segments must exist')
    timer_start = .15 + q_duration + .15
    reveal = timer_start + 3.0
    why_start = reveal + answer_duration + .18
    total = max(12.0, why_start + why_duration + .65)
    # Never truncate speech or accelerate it until it is unintelligible.
    if total > 15.5:
        raise ValueError(f'{total:.2f}s is too long: shorten editorial wording before publishing')
    return {'timer_start':timer_start,'reveal':reveal,'why_start':why_start,'total':total}


def render_video(question_obj, accent, out_mp4, tmp_dir, bg_music=None, day=1, slot=1, topic_name=None, viral_badge=None):
    q = prepare_content(question_obj)
    os.makedirs(tmp_dir, exist_ok=True)
    qvoice, avoice, wvoice = [os.path.join(tmp_dir, x + '.mp3') for x in ('question','answer','why')]
    letter, answer = LETTERS[q['correct_index']], q['options'][q['correct_index']]
    answer_text = q.get('speech_answer', ('सही जवाब: ' if LANG == 'hi' else 'The answer is ') + answer + '.')
    voice_fn = generate_voiceover
    # Voice outage is a render failure, not permission to post a silent clip.
    asyncio.run(voice_fn(q.get('speech_question',q['question']).replace(chr(34),''), answer_text, qvoice, avoice))
    unused = os.path.join(tmp_dir, 'unused.mp3')
    asyncio.run(voice_fn(q['explanation'], q['explanation'], wvoice, unused))
    plan = timing_plan(get_audio_duration(qvoice), get_audio_duration(avoice), get_audio_duration(wvoice))
    phases = [('question', None, plan['timer_start'])] + [('countdown', n, 1.) for n in (3,2,1)] + [('reveal',None,plan['why_start']-plan['reveal']),('explain',None,plan['total']-plan['why_start'])]
    images = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':1080,'height':1920}, device_scale_factor=1)
        for i,(phase,number,duration) in enumerate(phases):
            page.set_content(build_card(q,phase,number))
            page.evaluate('document.fonts.ready')
            # Shorts controls reserve x>=920, title/navigation reserve y>=1480.
            fits = page.evaluate('''() => {const m=document.querySelector('main'); return m.scrollHeight<=1240 && [...m.querySelectorAll('*')].every(e=>e.getBoundingClientRect().right<=896 && e.getBoundingClientRect().bottom<=1460);}''')
            if not fits: raise ValueError('Card overlaps Shorts safe area; shorten the wording')
            png = os.path.join(tmp_dir, f'{i}-{phase}.png'); page.screenshot(path=png); images.append(png)
        browser.close()
    listing = os.path.join(tmp_dir,'frames.txt')
    with open(listing,'w') as f:
        for png,(_,_,duration) in zip(images,phases):
            f.write(f"file '{png}'\nduration {duration:.6f}\n")
        f.write(f"file '{images[-1]}'\n")
    command = ['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',listing,'-i',qvoice,'-i',avoice,'-i',wvoice]
    filters = [f'[1:a]adelay=150:all=1[q]',f'[2:a]adelay={round(plan["reveal"]*1000)}:all=1[a]',f'[3:a]adelay={round(plan["why_start"]*1000)}:all=1[w]']
    labels=['[q]','[a]','[w]']
    # Three actual one-second beats; no ticking during the spoken question.
    for i in range(3):
        filters.append(f'sine=frequency=1000:duration=0.08,volume=0.12,afade=t=out:d=0.08,adelay={round((plan["timer_start"]+i)*1000)}:all=1[t{i}]'); labels.append(f'[t{i}]')
    filters.append(f'{"".join(labels)}amix=inputs=6:duration=longest:normalize=0,apad,alimiter=limit=0.95[mix]')
    command += ['-filter_complex',';'.join(filters),'-map','0:v','-map','[mix]','-t',str(plan['total']),'-vf','fps=30,format=yuv420p','-c:v','libx264','-preset','fast','-crf','18','-c:a','aac','-b:a','192k','-movflags','+faststart',out_mp4]
    subprocess.run(command,check=True)
    with open(os.path.join(tmp_dir,'timing.json'),'w') as f: json.dump(dict(plan,source_url=q['source_url'],question_id=q.get('id')),f,indent=2)
    print(f'Rendered checked {LANG} quiz: {plan["total"]:.2f}s, timer {plan["timer_start"]:.2f}-{plan["reveal"]:.2f}s')
