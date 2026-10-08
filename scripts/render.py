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
import json as _json, os as _os
REVIEWED = _json.load(open(_os.path.join(_os.path.dirname(__file__), '..', 'data', 'reviewed_en.json'), encoding='utf-8'))

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
    import html, math
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


def studio_html(q,t,plan):
 variant="2-studio-arena"
 import html, math
 esc=lambda x:html.escape(str(x),quote=True)
 logo_data=base64.b64encode(open(os.path.join(ASSETS,'logo.jpg'),'rb').read()).decode()
 font_name='1-QuizSans.ttf' if LANG=='en' else '3-QuizSans.ttf'
 font_data=base64.b64encode(open(os.path.join(ASSETS,'fonts',font_name),'rb').read()).decode()
 c={"bg":"#080f1e","ink":"#f5f6fa","muted":"#b7c6db","accent":"#f5b947","card":"#14253f","line":"#354660"};dark=variant.startswith('2');editorial=variant.startswith('3');reveal=t>=plan['reveal'];why=t>=plan['why_start'];count=plan['timer_start']<=t<plan['reveal'];n=max(1,3-int(t-plan['timer_start']))
 phase='THE ANSWER' if reveal else ('LOCK IT IN' if count else ('सवाल सुनिए' if LANG=='hi' else 'LISTEN. THEN CHOOSE.'))
 bg=''
 if dark:
  bg=f'<div class="studio-glow" style="transform:translateY({math.sin(t*.8)*28}px)"></div><div class="orbit" style="transform:rotate({t*6}deg)"></div>'
 else:
  bg=f'<div class="grid"></div><div class="ghost" style="transform:rotate({-12+t*.8}deg)">?</div>'
 logo=f'<header><img src="data:image/jpeg;base64,{logo_data}"><span>GK SNIPPETS{" HINDI" if LANG=="hi" else ""}</span><b>{esc(q["topic"])}</b></header>'
 headline='<h1>What does<br><span>"paper gold"</span><br>mean?</h1>'
 if dark: headline=f'<div class="kicker">{"अपना जवाब चुनिए" if LANG=="hi" else "CHOOSE YOUR ANSWER"}</div><h1>{esc(q["question"])}</h1>'
 illustration=''
 if editorial:
  headline='<div class="kicker">THE EXAM TRAP</div><h1>"Paper gold"<br>is not gold.</h1><div class="ask">So what is it?</div>'
  # The spoken question is identical; headline is a source-checked visual hook.
  illustration='<div class="mini-gold">▰ ▰ ▰ <span>?</span></div>'
 elif not dark:
  illustration='<div class="symbol"><span>Au</span><i>?</i></div>'
 opts=[]
 for i,text in enumerate(q["options"]):
  delay=i*.09;progress=min(1,max(0,(t-delay)/.35));dy=(1-progress)*45;opacity=.3+.7*progress
  cls='choice correct' if reveal and i==q["correct_index"] else ('choice wrong' if reveal else 'choice')
  opts.append(f'<div class="{cls}" style="transform:translateY({dy:.1f}px);opacity:{opacity}"><b>{"ABCD"[i]}</b><span>{esc(text)}</span>{"<em>✓</em>" if reveal and i==q["correct_index"] else ""}</div>')
 circumference=2*math.pi*58;fraction=(t-plan['timer_start'])%1 if count else 0
 timer=f'<div class="timer"><div><b>{phase}</b><span>{"You have 3 seconds." if count else ("Did you get it?" if reveal else "Listen. Then pick A, B, C or D.")}</span></div><svg width="160" height="160" viewBox="0 0 160 160"><circle cx="80" cy="80" r="58" fill="none" stroke="{c["line"]}" stroke-width="10"/><circle cx="80" cy="80" r="58" fill="none" stroke="{c["accent"]}" stroke-width="10" stroke-dasharray="{circumference}" stroke-dashoffset="{fraction*circumference}" transform="rotate(-90 80 80)"/><text x="80" y="103" text-anchor="middle" fill="{c["ink"]}" font-size="64" font-weight="800">{n if count else ("✓" if reveal else "?")}</text></svg></div>'
 payoff=f'<section class="payoff"><div class="kicker">{"जवाब की वजह" if LANG=="hi" else "THE TRAP, EXPLAINED"}</div><div class="answer-hero">{esc(q["options"][q["correct_index"]])}</div><div class="compare"><div><b>{esc(q.get("memory_key", "याद रखिए" if LANG=="hi" else "REMEMBER"))}</b><span>✓</span></div></div><p>{esc(q["explanation"])}</p><div class="source">{esc(q.get("source_label","Checked source"))}</div><div class="follow">{"रोज़ एक सवाल, साथ में वजह।" if LANG=="hi" else "FOLLOW FOR THE TRAP"}<small>{"सिर्फ जवाब नहीं, वजह भी।" if LANG=="hi" else "One question. One reason. Every day."}</small></div></section>'

 inner=payoff if why else f'{illustration}{headline}<div class="choices">{"".join(opts)}</div>{timer}'
 # Small fast scale at the reveal, never shrink the text below safe-area legibility.
 scale=1+(.015*max(0,1-(t-plan['reveal'])/.25) if reveal and not why else 0)
 css=f'''
 @font-face{{font-family:Quiz;src:url(data:font/ttf;base64,{font_data});font-weight:400}}*{{box-sizing:border-box}}body{{margin:0;width:1080px;height:1920px;overflow:hidden;background:{c['bg']};color:{c['ink']};font-family:Quiz,Arial}}.grid{{position:absolute;inset:0;background-image:linear-gradient({c['line']}55 1px,transparent 1px),linear-gradient(90deg,{c['line']}55 1px,transparent 1px);background-size:90px 90px}}.ghost{{position:absolute;font-size:1400px;line-height:1;color:{c['accent']}0c;right:-50px;top:250px;font-weight:900}}.studio-glow{{position:absolute;inset:-60px;background:radial-gradient(ellipse 1000px 600px at 50% 0%,rgba(20,38,77,.9),transparent 70%),radial-gradient(ellipse 800px 600px at 50% 100%,rgba(245,166,35,.2),transparent 75%)}}.orbit{{position:absolute;width:1200px;height:1200px;left:-100px;top:500px;border:2px solid #f5b94722;border-radius:50%;box-shadow:0 0 0 180px #f5b94708,0 0 0 340px #f5b94705}}main{{position:absolute;top:210px;left:72px;width:824px;height:1250px}}header{{height:70px;display:flex;align-items:center;gap:16px;font-size:27px;font-weight:800;letter-spacing:1px}}header img{{width:60px;height:60px;border-radius:15px}}header b{{margin-left:auto;color:{c['accent']};font-size:24px}}.content{{position:relative;margin-top:44px;transform:scale({scale})}}h1{{font-size:{'76' if editorial else '82'}px;line-height:1.09;letter-spacing:-2px;margin:0 0 35px;font-weight:800}}h1 span{{color:{c['accent']}}}.symbol{{position:absolute;right:30px;top:0;width:160px;height:180px;background:#f8dc7b;border:4px solid #d2a337;transform:rotate(8deg);color:#3e3014;padding:24px;box-shadow:12px 14px 0 #e8bd65}}.symbol span{{font-size:68px;font-weight:800}}.symbol i{{display:block;font-size:38px;font-style:normal;text-align:right}}.symbol+h1{{font-size:75px;max-width:650px}}.kicker{{font-size:28px;letter-spacing:3px;color:{c['accent']};font-weight:800;margin-bottom:25px}}.ask{{font-size:48px;font-weight:700;margin-top:-13px;margin-bottom:35px}}.mini-gold{{font-size:75px;color:#d2a337;float:right;margin-right:20px;line-height:1;transform:rotate(-7deg)}}.mini-gold span{{color:{c['ink']}}}.choices{{display:grid;grid-template-columns:{'1fr 1fr' if not editorial and not dark else '1fr'};gap:20px}}.choice{{position:relative;min-height:{'190' if not editorial and not dark else '130'}px;display:flex;align-items:{'flex-start' if not editorial and not dark else 'center'};flex-direction:{'column' if not editorial and not dark else 'row'};gap:16px;background:{c['card']};border:{'3px' if dark else '2px'} solid {c['line']};border-radius:{'26px' if not editorial else '4px'};padding:24px;box-shadow:{'0 12px 24px #0a162309' if not dark else 'none'};font-size:{'39' if not editorial else '42'}px;line-height:1.17;font-weight:700}}.choice b{{display:flex;align-items:center;justify-content:center;background:{c['accent']};color:white;font-size:28px;width:47px;height:47px;border-radius:11px;flex-shrink:0}}.choice.correct{{background:#d6f5e5;color:#124e37;border-color:#16a46b}}.choice.correct b{{background:#16a46b}}.choice em{{position:absolute;right:20px;top:20px;font-style:normal;font-size:40px;color:#168958}}.choice.wrong{{opacity:.35!important}}.timer{{display:flex;justify-content:space-between;align-items:center;border-top:3px solid {c['line']};margin-top:36px;padding-top:22px}}.timer b{{display:block;font-size:33px;color:{c['accent']};margin-bottom:14px}}.timer span{{font-size:29px}}.payoff{{padding-top:5px}}.sdr{{font-size:210px;font-weight:900;line-height:1;color:{c['accent']};letter-spacing:-5px}}.sdr span{{display:block;font-size:33px;letter-spacing:2px;margin-top:16px;color:{c['ink']}}}.compare{{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:55px}}.compare>div{{display:flex;justify-content:space-between;align-items:center;background:#d6f5e5;border-radius:22px;padding:30px;color:#155b3c}}.compare .not{{background:{c['card']};border:2px solid {c['line']};color:{c['muted']}}}.compare b{{font-size:41px;line-height:1.2}}.compare span{{font-size:100px;line-height:1}}.payoff p{{font-size:51px;line-height:1.25;margin:44px 0 27px;font-weight:700}}.source{{font-size:25px;color:{c['muted']}}}.follow{{margin-top:58px;background:{c['accent']};padding:26px;color:white;font-size:38px;line-height:1.3;font-weight:800;border-radius:{'16px' if not editorial else '0'}}}.follow small{{font-size:29px;font-weight:500;display:block;margin-top:9px}}
 '''
 css += '.answer-hero{font-size:76px;font-weight:800;line-height:1.15;color:#f5b947}.compare{grid-template-columns:1fr}.compare b{font-size:43px}.payoff p{font-size:49px}.content h1{font-size:74px;line-height:1.13}'
 if LANG=='hi':
  hindi_data=base64.b64encode(open(os.path.join(ASSETS,'fonts','4-QuizHindi.ttf'),'rb').read()).decode()
  css += f'@font-face{{font-family:Hindi;src:url(data:font/ttf;base64,{hindi_data});font-weight:400}}body{{font-family:Hindi,Quiz,Arial}}header{{font-family:Quiz,Arial}}'
 if editorial: css += 'h1{font-family:Georgia,serif;font-size:79px;line-height:1.05}.choice{border-left:7px solid #315aeb}.sdr{font-family:Georgia,serif}.follow{border-radius:0}'
 if dark: css += '.choice{min-height:123px;padding:23px 27px;font-size:43px}.content{margin-top:30px}.timer{margin-top:28px}.choice.correct{box-shadow:0 0 45px #16a46b44}.follow{color:#182435}'
 if LANG=='hi':
  inner=inner.replace('THE ANSWER','सही जवाब').replace('LOCK IT IN','अपना जवाब चुनिए').replace('QUICK GK / ECONOMY','सवाल सुनिए').replace('You have 3 seconds.','तीन सेकंड।').replace('Did you get it?','आपका जवाब सही था?').replace('Listen. Then pick A, B, C or D.','सुनिए, फिर जवाब चुनिए।')
 return f'<!doctype html><meta charset="utf-8"><style>{css}</style>{bg}<main>{logo}<div class="content">{inner}</div></main>'

def render_video(question_obj, accent, out_mp4, tmp_dir, bg_music=None, day=1, slot=1, topic_name=None, viral_badge=None):
    from pathlib import Path
    import math
    q=prepare_content(question_obj)
    d=Path(tmp_dir);d.mkdir(parents=True,exist_ok=True)
    paths=[str(d/(n+'.mp3')) for n in ('question','answer','why')]
    fn=generate_voiceover if LANG=='en' else generate_voiceover_hindi
    answer=q.get('speech_answer',q['options'][q['correct_index']]+'.')
    asyncio.run(fn(q.get('speech_question',q['question']).replace(chr(34),''),answer,paths[0],paths[1]))
    asyncio.run(fn(q['explanation'],q['explanation'],paths[2],str(d/'unused.mp3')))
    plan=timing_plan(*[get_audio_duration(p) for p in paths])
    fps=15
    with sync_playwright() as p:
        b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page(viewport={'width':1080,'height':1920})
        for i in range(math.ceil(plan['total']*fps)):
            page.set_content(studio_html(q,i/fps,plan));page.evaluate('document.fonts.ready')
            if i in (0,math.ceil(plan['why_start']*fps)+1):
                overflow=page.evaluate("() => [...document.querySelectorAll('main *')].some(e=>{let r=e.getBoundingClientRect();return r.right>900||r.bottom>1480})")
                if overflow:raise ValueError('Shorts safe-area overflow; shorten reviewed wording')
            page.screenshot(path=str(d/f'{i:04d}.png'))
        b.close()
    music=bg_music if bg_music and os.path.isfile(bg_music) else os.path.join(ASSETS,'audio','slot1_one_answer_left.mp3')
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate',str(fps),'-i',str(d/'%04d.png')]
    for path in paths:cmd+=['-i',path]
    cmd+=['-stream_loop','-1','-i',music]
    f=[f'[1:a]adelay=150:all=1[q]',f'[2:a]adelay={round(plan["reveal"]*1000)}:all=1[a]',f'[3:a]adelay={round(plan["why_start"]*1000)}:all=1[w]',f'[4:a]atrim=duration={plan["total"]},volume=0.05,afade=t=out:st={plan["total"]-.6}:d=0.6[bed]']
    for i in range(3):f.append(f'sine=frequency=1000:duration=0.08,volume=0.12,afade=t=out:d=0.08,adelay={round((plan["timer_start"]+i)*1000)}:all=1[t{i}]')
    f.append('[q][a][w][bed][t0][t1][t2]amix=inputs=7:duration=longest:normalize=0,apad,alimiter=limit=0.95[mix]')
    cmd+=['-filter_complex',';'.join(f),'-map','0:v','-map','[mix]','-t',str(plan['total']),'-vf','fps=30,format=yuv420p','-c:v','libx264','-crf','18','-preset','fast','-c:a','aac','-b:a','192k','-movflags','+faststart',out_mp4]
    subprocess.run(cmd,check=True)
    (d/'timing.json').write_text(json.dumps(dict(plan,source_url=q['source_url'],question_id=q['id'],style='studio-arena'),indent=2))
    print(f"Studio arena {LANG}: {plan['total']:.2f}s")
