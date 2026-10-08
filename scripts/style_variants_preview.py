"""Local-only style comparison. No uploads, credentials or state writes.
Uses q0075's source-checked content and previously generated speech segments.
"""
import os,json,base64,math,subprocess,argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE=Path(__file__).resolve().parents[1]
FONT=base64.b64encode((BASE/'assets/fonts/1-QuizSans.ttf').read_bytes()).decode()
LOGO=base64.b64encode((BASE/'assets/logo.jpg').read_bytes()).decode()
OPTIONS=['IMF Special Drawing Rights','World Bank loans','Gold-backed currencies','Deficit financing']
SOURCE='https://www.imf.org/en/topics/special-drawing-right'
THEMES={
 '1-white-lab':{'bg':'#f7f7f3','ink':'#162433','muted':'#617080','accent':'#ef6a32','card':'#ffffff','line':'#dce1e7','name':'White quiz lab'},
 '2-studio-arena':{'bg':'#080f1e','ink':'#f5f6fa','muted':'#b7c6db','accent':'#f5b947','card':'#14253f','line':'#354660','name':'Studio arena'},
 '3-paper-editorial':{'bg':'#fffaf2','ink':'#181f29','muted':'#5b6269','accent':'#315aeb','card':'#ffffff','line':'#d4d4ca','name':'Paper editorial'},
}
def page_html(variant,t,plan):
 c=THEMES[variant];dark=variant.startswith('2');editorial=variant.startswith('3');reveal=t>=plan['reveal'];why=t>=plan['why_start'];count=plan['timer_start']<=t<plan['reveal'];n=max(1,3-int(t-plan['timer_start']))
 phase='THE ANSWER' if reveal else ('LOCK IT IN' if count else 'QUICK GK / ECONOMY')
 bg=''
 if dark:
  bg=f'<div class="studio-glow" style="transform:translateY({math.sin(t*.8)*28}px)"></div><div class="orbit" style="transform:rotate({t*6}deg)"></div>'
 else:
  bg=f'<div class="grid"></div><div class="ghost" style="transform:rotate({-12+t*.8}deg)">?</div>'
 logo=f'<header><img src="data:image/jpeg;base64,{LOGO}"><span>GK SNIPPETS</span><b>01 / ECONOMY</b></header>'
 headline='<h1>What does<br><span>"paper gold"</span><br>mean?</h1>'
 if dark: headline='<div class="kicker">CHOOSE YOUR ANSWER</div><h1>What is<br><span>"paper gold"?</span></h1>'
 illustration=''
 if editorial:
  headline='<div class="kicker">THE EXAM TRAP</div><h1>"Paper gold"<br>is not gold.</h1><div class="ask">So what is it?</div>'
  # The spoken question is identical; headline is a source-checked visual hook.
  illustration='<div class="mini-gold">▰ ▰ ▰ <span>?</span></div>'
 elif not dark:
  illustration='<div class="symbol"><span>Au</span><i>?</i></div>'
 opts=[]
 for i,text in enumerate(OPTIONS):
  delay=i*.09;progress=min(1,max(0,(t-delay)/.35));dy=(1-progress)*45;opacity=.3+.7*progress
  cls='choice correct' if reveal and i==0 else ('choice wrong' if reveal else 'choice')
  opts.append(f'<div class="{cls}" style="transform:translateY({dy:.1f}px);opacity:{opacity}"><b>{"ABCD"[i]}</b><span>{text}</span>{"<em>✓</em>" if reveal and i==0 else ""}</div>')
 circumference=2*math.pi*58;fraction=(t-plan['timer_start'])%1 if count else 0
 timer=f'<div class="timer"><div><b>{phase}</b><span>{"You have 3 seconds." if count else ("Did you get it?" if reveal else "Listen. Then pick A, B, C or D.")}</span></div><svg width="160" height="160" viewBox="0 0 160 160"><circle cx="80" cy="80" r="58" fill="none" stroke="{c["line"]}" stroke-width="10"/><circle cx="80" cy="80" r="58" fill="none" stroke="{c["accent"]}" stroke-width="10" stroke-dasharray="{circumference}" stroke-dashoffset="{fraction*circumference}" transform="rotate(-90 80 80)"/><text x="80" y="103" text-anchor="middle" fill="{c["ink"]}" font-size="64" font-weight="800">{n if count else ("✓" if reveal else "?")}</text></svg></div>'
 payoff=f'<section class="payoff"><div class="kicker">THE TRAP, EXPLAINED</div><div class="sdr">SDR<span>SPECIAL DRAWING RIGHTS</span></div><div class="compare"><div><b>RESERVE<br>ASSET</b><span>✓</span></div><div class="not"><b>NOT<br>GOLD</b><span>×</span></div></div><p>SDRs are reserve assets,<br>not currency or physical gold.</p><div class="source">Source: IMF / Special Drawing Rights</div><div class="follow">FOLLOW FOR THE TRAP<br><small>One question. One reason. Every day.</small></div></section>'
 inner=payoff if why else f'{illustration}{headline}<div class="choices">{"".join(opts)}</div>{timer}'
 # Small fast scale at the reveal, never shrink the text below safe-area legibility.
 scale=1+(.015*max(0,1-(t-plan['reveal'])/.25) if reveal and not why else 0)
 css=f'''
 @font-face{{font-family:Quiz;src:url(data:font/ttf;base64,{FONT});font-weight:400}}*{{box-sizing:border-box}}body{{margin:0;width:1080px;height:1920px;overflow:hidden;background:{c['bg']};color:{c['ink']};font-family:Quiz,Arial}}.grid{{position:absolute;inset:0;background-image:linear-gradient({c['line']}55 1px,transparent 1px),linear-gradient(90deg,{c['line']}55 1px,transparent 1px);background-size:90px 90px}}.ghost{{position:absolute;font-size:1400px;line-height:1;color:{c['accent']}0c;right:-50px;top:250px;font-weight:900}}.studio-glow{{position:absolute;inset:-60px;background:radial-gradient(ellipse 1000px 600px at 50% 0%,rgba(20,38,77,.9),transparent 70%),radial-gradient(ellipse 800px 600px at 50% 100%,rgba(245,166,35,.2),transparent 75%)}}.orbit{{position:absolute;width:1200px;height:1200px;left:-100px;top:500px;border:2px solid #f5b94722;border-radius:50%;box-shadow:0 0 0 180px #f5b94708,0 0 0 340px #f5b94705}}main{{position:absolute;top:210px;left:72px;width:824px;height:1250px}}header{{height:70px;display:flex;align-items:center;gap:16px;font-size:27px;font-weight:800;letter-spacing:1px}}header img{{width:60px;height:60px;border-radius:15px}}header b{{margin-left:auto;color:{c['accent']};font-size:24px}}.content{{position:relative;margin-top:44px;transform:scale({scale})}}h1{{font-size:{'76' if editorial else '82'}px;line-height:1.09;letter-spacing:-2px;margin:0 0 35px;font-weight:800}}h1 span{{color:{c['accent']}}}.symbol{{position:absolute;right:30px;top:0;width:160px;height:180px;background:#f8dc7b;border:4px solid #d2a337;transform:rotate(8deg);color:#3e3014;padding:24px;box-shadow:12px 14px 0 #e8bd65}}.symbol span{{font-size:68px;font-weight:800}}.symbol i{{display:block;font-size:38px;font-style:normal;text-align:right}}.symbol+h1{{font-size:75px;max-width:650px}}.kicker{{font-size:28px;letter-spacing:3px;color:{c['accent']};font-weight:800;margin-bottom:25px}}.ask{{font-size:48px;font-weight:700;margin-top:-13px;margin-bottom:35px}}.mini-gold{{font-size:75px;color:#d2a337;float:right;margin-right:20px;line-height:1;transform:rotate(-7deg)}}.mini-gold span{{color:{c['ink']}}}.choices{{display:grid;grid-template-columns:{'1fr 1fr' if not editorial and not dark else '1fr'};gap:20px}}.choice{{position:relative;min-height:{'190' if not editorial and not dark else '130'}px;display:flex;align-items:{'flex-start' if not editorial and not dark else 'center'};flex-direction:{'column' if not editorial and not dark else 'row'};gap:16px;background:{c['card']};border:{'3px' if dark else '2px'} solid {c['line']};border-radius:{'26px' if not editorial else '4px'};padding:24px;box-shadow:{'0 12px 24px #0a162309' if not dark else 'none'};font-size:{'39' if not editorial else '42'}px;line-height:1.17;font-weight:700}}.choice b{{display:flex;align-items:center;justify-content:center;background:{c['accent']};color:white;font-size:28px;width:47px;height:47px;border-radius:11px;flex-shrink:0}}.choice.correct{{background:#d6f5e5;color:#124e37;border-color:#16a46b}}.choice.correct b{{background:#16a46b}}.choice em{{position:absolute;right:20px;top:20px;font-style:normal;font-size:40px;color:#168958}}.choice.wrong{{opacity:.35!important}}.timer{{display:flex;justify-content:space-between;align-items:center;border-top:3px solid {c['line']};margin-top:36px;padding-top:22px}}.timer b{{display:block;font-size:33px;color:{c['accent']};margin-bottom:14px}}.timer span{{font-size:29px}}.payoff{{padding-top:5px}}.sdr{{font-size:210px;font-weight:900;line-height:1;color:{c['accent']};letter-spacing:-5px}}.sdr span{{display:block;font-size:33px;letter-spacing:2px;margin-top:16px;color:{c['ink']}}}.compare{{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:55px}}.compare>div{{display:flex;justify-content:space-between;align-items:center;background:#d6f5e5;border-radius:22px;padding:30px;color:#155b3c}}.compare .not{{background:{c['card']};border:2px solid {c['line']};color:{c['muted']}}}.compare b{{font-size:41px;line-height:1.2}}.compare span{{font-size:100px;line-height:1}}.payoff p{{font-size:51px;line-height:1.25;margin:44px 0 27px;font-weight:700}}.source{{font-size:25px;color:{c['muted']}}}.follow{{margin-top:58px;background:{c['accent']};padding:26px;color:white;font-size:38px;line-height:1.3;font-weight:800;border-radius:{'16px' if not editorial else '0'}}}.follow small{{font-size:29px;font-weight:500;display:block;margin-top:9px}}
 '''
 if editorial: css += 'h1{font-family:Georgia,serif;font-size:79px;line-height:1.05}.choice{border-left:7px solid #315aeb}.sdr{font-family:Georgia,serif}.follow{border-radius:0}'
 if dark: css += '.choice{min-height:123px;padding:23px 27px;font-size:43px}.content{margin-top:30px}.timer{margin-top:28px}.choice.correct{box-shadow:0 0 45px #16a46b44}.follow{color:#182435}'
 return f'<!doctype html><meta charset="utf-8"><style>{css}</style>{bg}<main>{logo}<div class="content">{inner}</div></main>'
def render(variant,audio_dir,out_dir,fps=15):
 a=Path(audio_dir);out=Path(out_dir);out.mkdir(parents=True,exist_ok=True);plan=json.loads((a/'timing.json').read_text());d=out/variant;d.mkdir(exist_ok=True)
 with sync_playwright() as p:
  b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page(viewport={'width':1080,'height':1920})
  for i in range(math.ceil(plan['total']*fps)):
   t=i/fps
   if (d/f'{i:04d}.png').exists():continue
   page.set_content(page_html(variant,t,plan));page.evaluate('document.fonts.ready')
   if i in [0,math.ceil(plan['why_start']*fps)+1]:
    overflow=page.evaluate('''() => [...document.querySelectorAll('main *')].filter(e=> {let r=e.getBoundingClientRect();return r.right>900||r.bottom>1480}).map(e=>e.className)''')
    if overflow:raise ValueError('Safe-area overflow '+str(overflow))
   page.screenshot(path=str(d/f'{i:04d}.png'))
  b.close()
 mp4=out/f'GK-variant-{variant}.mp4'
 cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate',str(fps),'-i',str(d/'%04d.png'),'-i',str(a/'question.mp3'),'-i',str(a/'answer.mp3'),'-i',str(a/'why.mp3'),'-stream_loop','-1','-i',str(BASE/'assets/audio/slot1_one_answer_left.mp3')]
 f=[f'[1:a]adelay=150:all=1[q]',f'[2:a]adelay={round(plan["reveal"]*1000)}:all=1[a]',f'[3:a]adelay={round(plan["why_start"]*1000)}:all=1[w]',f'[4:a]atrim=duration={plan["total"]},volume=0.05,afade=t=out:st={plan["total"]-.6}:d=0.6[bed]']
 for i in range(3):f.append(f'sine=frequency=1000:duration=0.08,volume=.12,afade=t=out:d=0.08,adelay={round((plan["timer_start"]+i)*1000)}:all=1[t{i}]')
 f.append('[q][a][w][bed][t0][t1][t2]amix=inputs=7:duration=longest:normalize=0,apad,alimiter=limit=.95[mix]')
 cmd+=['-filter_complex',';'.join(f),'-map','0:v','-map','[mix]','-t',str(plan['total']),'-vf','fps=30,format=yuv420p','-c:v','libx264','-crf','18','-preset','fast','-c:a','aac','-b:a','192k','-movflags','+faststart',str(mp4)];subprocess.run(cmd,check=True);print(mp4)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--variant',choices=THEMES,required=True);p.add_argument('--audio-dir',required=True);p.add_argument('--out-dir',required=True);a=p.parse_args();render(a.variant,a.audio_dir,a.out_dir)
