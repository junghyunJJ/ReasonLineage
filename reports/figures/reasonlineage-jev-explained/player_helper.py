"""Create a native SVG animation and GIF/MP4 exports; never edits the source bitmap."""
import hashlib
import html
import io
import json
import math
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'pyproject.toml').is_file())
sys.path.insert(0, str(ROOT / '.superpowers/figure-animation-deps'))
import cairosvg
import imageio_ffmpeg
from PIL import Image

OUT = ROOT / 'reports/figures/reasonlineage-animation'
FPS, LENGTH = 15, 25
COLORS = {'a':'#2987d7','b':'#e65b91','c':'#e8a037','d':'#8a66d7'}
MODELS = [('Opus 5.5','Anthropic','a'),('GPT-6.1 sol','OpenAI','b'),('Grok 4.7','xAI','c'),('GLM-5.3-flash','Z.ai','d')]
NODES = {
    'A0':{'author':'Opus 5.5','parents':[],'colors':['a'],'generation':0},
    'B0':{'author':'GPT-6.1 sol','parents':[],'colors':['b'],'generation':0},
    'C0':{'author':'Grok 4.7','parents':[],'colors':['c'],'generation':0},
    'D0':{'author':'GLM-5.3-flash','parents':[],'colors':['d'],'generation':0},
    'M1':{'author':'Opus 5.5','parents':['A0'],'colors':['a'],'generation':1},
    'X1':{'author':'Grok 4.7','parents':['A0','B0'],'colors':['a','b'],'generation':1},
    'M2':{'author':'Opus 5.5','parents':['M1'],'colors':['a'],'generation':2},
    'X2':{'author':'GLM-5.3-flash','parents':['M1','X1'],'colors':['a','b'],'generation':2},
}
CHAPTERS = [
 (0,'Generate','네 모델이 각각 후보 답변을 생성합니다.'),
 (3.2,'jev checks','jev가 답변의 구조·완성도·과제 요구 요소를 점검합니다.'),
 (5,'Critic scoring','작성자를 제외한 LLM 비판으로 fitness를 계산합니다.'),
 (5.8,'Select parents','후보 중 두 개를 부모 답변으로 선택합니다.'),
 (8,'Mutation & crossover','원래 작성자의 변이와 다른 모델의 교차로 새 답변 두 개를 만듭니다.'),
 (10,'Generation 1','생존 부모 두 개와 새 후보 두 개가 다음 세대를 이룹니다.'),
 (12,'Evaluate new responses','새 후보만 다시 점검합니다. 부모는 기존 점수를 유지합니다.'),
 (13.8,'Critic scoring','새 후보의 비판·채점을 마친 뒤 네 후보를 비교합니다.'),
 (14.4,'Select next parents','이번 개념 예시에서는 새 후보 두 개가 다음 부모가 됩니다.'),
 (16,'Evolve again','부모의 계보를 유지하면서 변이·교차를 한 번 더 수행합니다.'),
 (18,'Generation 2','다시 부모 두 개와 새 후보 두 개가 모입니다.'),
 (20,'Final evaluation','새 후보의 jev 점검과 LLM 비판·채점을 마칩니다.'),
 (21.6,'Choose final response','평가가 끝난 후보 중 최종 답변을 선택합니다.'),
 (23,'Final response','계보와 평가 기록을 남긴 최종 답변입니다. 개념 예시이며 실제 모델 순위가 아닙니다.'),
]
SEED={k:(228,215+i*101) for i,k in enumerate(['A0','B0','C0','D0'])}
EV0={k:(311+i*46,380) for i,k in enumerate(['A0','B0','C0','D0'])}
PARENTS=[(620,263),(770,263)]
CHILDREN=[(610,451),(784,451)]
POOL=[(976,271),(1084,271),(976,410),(1084,410)]
EV1=[(350,380),(418,380)]


def smooth(p):
    p=max(0,min(1,p));return p*p*(3-2*p)


def mix(a,b,p):
    return tuple(x+(y-x)*smooth(p) for x,y in zip(a,b))


def row(cid,pos,alpha=1,scale=1):
    return {'id':cid,'x':pos[0],'y':pos[1],'opacity':alpha,'scale':scale}


def loop_move(start,end,p):
    points=[start,(1030,562),(380,562),end]
    q=max(0,min(.999999,p))*3;index=int(q)
    return mix(points[index],points[index+1],q-index)


def scene(t):
    t=max(0,min(LENGTH,t));items=[]
    if t<3.2:
        for i,cid in enumerate(SEED):
            p=(t-.3-i*.25)/1.8
            items.append(row(cid,mix((120,SEED[cid][1]),SEED[cid],p),smooth(p)))
    elif t<5.8:
        for cid in SEED:items.append(row(cid,mix(SEED[cid],EV0[cid],(t-3.2)/1.25),1,.72))
    elif t<8:
        for cid,target in [('A0',PARENTS[0]),('B0',PARENTS[1]),('C0',(550,262)),('D0',(847,262))]:
            p=(t-5.8)/1.5;items.append(row(cid,mix(EV0[cid],target,p),1 if cid in ['A0','B0'] else 1-smooth(p)*.92))
    elif t<10:
        items=[row('A0',PARENTS[0]),row('B0',PARENTS[1])]
        p=(t-8)/1.4
        items.extend([row('M1',mix(PARENTS[0],CHILDREN[0],p),smooth(p)),row('X1',mix((695,263),CHILDREN[1],p),smooth(p))])
    elif t<12:
        items=[row(cid,mix(start,end,(t-10)/1.4)) for cid,start,end in zip(['A0','B0','M1','X1'],PARENTS+CHILDREN,POOL)]
    elif t<14.4:
        items=[row('A0',POOL[0],.6),row('B0',POOL[1],.6)]
        items.extend(row(cid,loop_move(start,end,smooth((t-12)/1.4))) for cid,start,end in zip(['M1','X1'],POOL[2:],EV1))
    elif t<16:
        p=(t-14.4)/1.15
        items=[row('A0',POOL[0],.6*(1-smooth(p))),row('B0',POOL[1],.6*(1-smooth(p)))]
        items.extend(row(cid,mix(start,end,p)) for cid,start,end in zip(['M1','X1'],EV1,PARENTS))
    elif t<18:
        items=[row('M1',PARENTS[0]),row('X1',PARENTS[1])];p=(t-16)/1.3
        items.extend([row('M2',mix(PARENTS[0],CHILDREN[0],p),smooth(p)),row('X2',mix((695,263),CHILDREN[1],p),smooth(p))])
    elif t<20:
        items=[row(cid,mix(start,end,(t-18)/1.3)) for cid,start,end in zip(['M1','X1','M2','X2'],PARENTS+CHILDREN,POOL)]
    elif t<21.6:
        items=[row('M1',POOL[0],.6),row('X1',POOL[1],.6)]
        items.extend(row(cid,loop_move(start,end,smooth((t-20)/.7))) for cid,start,end in zip(['M2','X2'],POOL[2:],EV1))
    else:
        p=(t-21.6)/1.2
        items=[row('M1',POOL[0],.25),row('X1',POOL[1],.25),row('X2',EV1[1],1-smooth(p)*.85),
               row('M2',mix(EV1[0],(1200,350),p))]
    chapter=max(i for i,c in enumerate(CHAPTERS) if c[0]<=t)
    stage=0 if t<3.2 else 1 if t<5.8 or 12<=t<14.4 or 20<=t<21.6 else 2 if 5.8<=t<10 or 14.4<=t<18 else 3
    return items,chapter,stage


def text(x,y,value,size=16,color='#172c47',weight=400,anchor='middle'):
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{html.escape(str(value))}</text>'


def rect(x,y,w,h,fill='#fff',stroke='#dce4ed',radius=12,extra=''):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" {extra}/>'


def card(item):
    cid=item['id'];n=NODES[cid];colors=[COLORS[c] for c in n['colors']];w,h=48,65
    x,y=item['x']-w/2,item['y']-h/2
    s=f'<g opacity="{item["opacity"]:.3f}" transform="translate({item["x"]} {item["y"]}) scale({item["scale"]}) translate({-item["x"]} {-item["y"]})">'
    s+=f'<path d="M{x},{y} h{w-10} l10,10 v{h-10} h{-w} z" fill="#fff" stroke="{colors[0]}" stroke-width="2.6"/>'
    for i in range(4):
        color=colors[i%len(colors)];length=24 if i%2==0 else 18+n['generation']*3
        s+=f'<path d="M{x+9},{y+18+i*8} h{length}" stroke="{color}" stroke-width="3.2" stroke-linecap="round"/>'
    if n['generation']:
        s+=f'<circle cx="{x+w-7}" cy="{y+h-7}" r="5" fill="#eab940"/>'
    s+=text(item['x'],y+h+18,cid,13,colors[0],700)
    return s+'</g>'


def svg(t):
    items,chapter,stage=scene(t);parts=[]
    parts.append('<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"><defs><marker id="arr" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#8798ab"/></marker><marker id="blue" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#2987d7"/></marker><marker id="pink" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#e65b91"/></marker></defs><g font-family="DejaVu Sans, sans-serif">')
    parts.append(rect(0,0,1280,720,'#fff','#fff',0))
    parts.append(text(640,45,'ReasonLineage · Evolution in motion',29,weight=700))
    parts.append(text(640,77,'Candidate responses evolve through evaluation, selection, mutation and crossover',15,'#62758b'))
    for i,(x,label) in enumerate([(140,'Generate'),(383,'Evaluate'),(693,'Select & evolve'),(1029,'Next generation')]):
        active=i==stage;parts.append(rect(x-107,112,214,42,'#e9f6f1' if active else '#f4f7fa','#cadfd5' if active else '#e4eaf1',20))
        parts.append(text(x,139,str(i+1)+'  '+label,18,'#086448' if active else '#677a90',700))
    for i,(model,provider,color) in enumerate(MODELS):
        y=215+i*101
        parts.append(rect(28,y-31,155,65,'#f6f8fb','#d5dfe9',8))
        parts.append(text(105,y-4,model,15,weight=700));parts.append(text(105,y+19,provider,13,'#677a90'))
        parts.append(f'<path d="M185,{y} H198" stroke="#9baabd" stroke-width="2" marker-end="url(#arr)"/>')
    parts.append(text(227,579,'G0',20,weight=700))
    parts.append(rect(281,174,207,330,'#f0faf5','#b5dccb'))
    parts.append(text(384,215,'jev',35,'#096f4f',700));parts.append(text(384,242,'Structural evaluation',14,'#096f4f',600))
    for y,label in [(273,'Structure'),(300,'Completeness'),(327,'Task requirements')]:
        active=t>=3.2;parts.append(f'<circle cx="307" cy="{y-5}" r="8" fill="{"#26a16f" if active else "#c7d9d0"}"/>')
        if active:parts.append(f'<path d="M303,{y-5} l3,3 l5,-6" stroke="#fff" stroke-width="2" fill="none"/>')
        parts.append(text(324,y,label,13,'#2d604d',anchor='start'))
    critic=5<=t<5.8 or 13.8<=t<14.4 or 20.8<=t<21.6
    parts.append(rect(295,439,180,51,'#e5edf5' if critic else '#f4f7fa','#bdcddd',8))
    parts.append(text(385,460,'LLM critique → fitness',13,'#355270',700));parts.append(text(385,478,'Non-author critics',11,'#60748a'))
    parts.append(text(695,191,'Select two responses',18,weight=700))
    for x in [620,770]:parts.append(rect(x-31,222,62,82,'#f8fafc','#e1e7ee',8))
    show=t>=8
    for x,label,sub in [(610,'Mutation','Original author'),(784,'Crossover','Other LLM')]:
        parts.append(rect(x-72,326,144,180,'#f7faff' if label=='Mutation' else '#fff6fa','#d1dfee' if label=='Mutation' else '#ecd0dc',10))
        parts.append(text(x,351,label,20,weight=700));parts.append(text(x,375,sub,12,'#60738a'))
    if show:
        for d,c in [('M620,306 Q612,311 610,325','blue'),('M620,306 Q698,304 764,325','blue'),('M770,306 Q778,311 784,325','pink')]:
            parts.append(f'<path d="{d}" stroke="{COLORS["a" if c=="blue" else "b"]}" stroke-width="2.3" fill="none" marker-end="url(#{c})"/>')
    generation=0 if t<10 else 1 if t<18 else 2
    parts.append(rect(929,173,201,349,'#f7faff','#d2e3f0'))
    parts.append(text(1030,204,'G'+str(max(1,generation)),22,weight=700))
    parts.append(text(1030,221,'Retained parents',13,'#748399'))
    parts.append(text(1030,365,'New offspring',13,'#748399'))
    for x,y in POOL:parts.append(rect(x-28,y-39,56,77,'#fff','#dce5ef',8))
    parts.append(text(1200,257,'Final',18,weight=700));parts.append(text(1200,279,'response',18,weight=700))
    parts.append(rect(1170,309,60,83,'#f5faf7','#c1d9cc',8))
    parts.append(text(1200,428,'After evaluation',11,'#71869a'))
    for x,y,x2 in [(250,380,270),(500,380,518),(874,380,918),(1136,350,1160)]:
        parts.append(f'<path d="M{x},{y} H{x2}" stroke="#a8b6c4" stroke-width="2.3" marker-end="url(#arr)"/>')
    parts.append('<path d="M1030,523 V553 Q1030,570 1014,570 H403 Q383,570 383,550 V514" fill="none" stroke="#b5c1cc" stroke-width="2.8" marker-end="url(#arr)"/>')
    parts.append(text(694,592,'Repeat · evaluate new offspring; retain saved parent scores',12,'#697b8f'))
    parts.extend(card(item) for item in items)
    parts.append(rect(35,614,1210,78,'#f6f8fb','#e8edf2',12))
    parts.append(text(640,642,CHAPTERS[chapter][1],21,'#193953',700))
    captions=['One candidate response from each model.','jev checks structural completeness and task requirements.','Fitness comes from isolated, non-author LLM critiques.','Two responses survive; unselected candidates fade.','Mutation refines one parent; crossover combines two parents.','Two retained parents + two new offspring.','Only new offspring are inspected; parents retain saved scores.','Critics score the new offspring before the next selection.','The next parents are selected from the evaluated population.','New descendants preserve their parent relationships.','A new population forms with deeper response lineages.','New responses receive structural checks and critic scoring.','Final selection happens after evaluation.','A selected response with its recorded lineage.']
    parts.append(text(640,670,captions[chapter],14,'#62758b'))
    parts.append('</g></svg>');return ''.join(parts)


def html_player(frames):
    data=json.dumps({'fps':FPS,'duration':LENGTH,'frames':frames,'chapters':CHAPTERS},ensure_ascii=False).replace('<','\\u003c')
    return '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ReasonLineage 진화 애니메이션</title>
<style>body{font:15px/1.5 system-ui,sans-serif;background:#edf2f7;color:#173047;margin:0;padding:20px}.app{max-width:1320px;margin:auto}header{display:flex;align-items:center;justify-content:space-between;gap:12px}h1{font-size:21px}header span{color:#64788b;font-size:13px}#screen{background:white;border-radius:14px;border:1px solid #dbe4ec;overflow:hidden}#screen svg{width:100%;height:auto;display:block}.controls{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:14px 0}button,select{font:inherit;padding:8px 12px;border:1px solid #b6c7d6;background:white;border-radius:7px;cursor:pointer}button:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid #3b8edd}#play{background:#116c52;color:white;min-width:90px}#seek{flex:1;min-width:180px}#time{font-variant-numeric:tabular-nums}#caption{background:white;border-radius:10px;padding:16px;margin:12px 0;min-height:28px}.note{color:#697d90;font-size:13px}label{display:flex;align-items:center;gap:4px}@media(max-width:600px){body{padding:8px}header{display:block}.controls{gap:6px}button,select{padding:6px}#seek{flex-basis:100%}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}</style>
<main class="app"><header><h1>ReasonLineage · 진화 과정</h1><span>개념 애니메이션 · 4모델 구성</span></header><div id="screen" role="img" aria-label="ReasonLineage 후보 생성과 평가, 변이·교차의 진화 과정"></div>
<div class="controls"><button id="play" aria-label="재생">재생</button><button id="prev">이전 단계</button><button id="next">다음 단계</button><input id="seek" aria-label="재생 위치" type="range" min="0" max="25" step="0.01" value="0"><span id="time">0.0 / 25.0초</span><select id="speed" aria-label="재생 속도"><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="1.5">1.5×</option><option value="2">2×</option></select><label><input id="loop" type="checkbox" checked>반복</label></div>
<div id="caption" aria-live="polite"></div><p class="note">jev는 구조 점검과 피드백을 담당하고, LLM 비판 점수로 생존자를 선택합니다. 색상과 선택 결과는 원리를 설명하는 예시이며 실제 모델 순위를 뜻하지 않습니다. 새 후보만 다시 평가하며 부모는 기존 점수를 유지합니다. 키보드: Space 재생/정지 · ←/→ 단계 이동.</p></main>
<script>const DATA=__DATA__;let position=0,playing=!window.matchMedia('(prefers-reduced-motion: reduce)').matches,last=0,rendered=-1;
const by=id=>document.getElementById(id);
function chapterAt(t){let n=0;DATA.chapters.forEach((c,i)=>{if(c[0]<=t)n=i});return n;}
function paint(){const f=Math.min(DATA.frames.length-1,Math.floor(position*DATA.fps));if(f!==rendered){by('screen').innerHTML=DATA.frames[f];rendered=f;}by('seek').value=position;by('time').textContent=position.toFixed(1)+' / '+DATA.duration.toFixed(1)+'초';by('caption').textContent=DATA.chapters[chapterAt(position)][2];by('play').textContent=playing?'일시정지':'재생';by('play').setAttribute('aria-label',playing?'일시정지':'재생');}
function toggle(){if(position>=DATA.duration)position=0;playing=!playing;last=0;paint();}
function jump(direction){playing=false;let k=chapterAt(position);if(direction<0&&position-DATA.chapters[k][0]>.2)position=DATA.chapters[k][0];else position=DATA.chapters[Math.max(0,Math.min(DATA.chapters.length-1,k+direction))][0];last=0;paint();}
function tick(now){if(playing&&last){position+=(now-last)/1000*Number(by('speed').value);if(position>=DATA.duration){position=by('loop').checked?position%DATA.duration:DATA.duration;if(!by('loop').checked)playing=false;}paint();}last=now;requestAnimationFrame(tick);}
by('play').addEventListener('click',toggle);by('prev').addEventListener('click',()=>jump(-1));by('next').addEventListener('click',()=>jump(1));by('seek').addEventListener('input',()=>{position=Number(by('seek').value);last=0;paint();});
document.addEventListener('keydown',e=>{if(['INPUT','SELECT','BUTTON','TEXTAREA'].includes(e.target.tagName))return;if(e.code==='Space'){e.preventDefault();toggle();}if(e.code==='ArrowRight'){e.preventDefault();jump(1);}if(e.code==='ArrowLeft'){e.preventDefault();jump(-1);}});
paint();requestAnimationFrame(tick);</script></html>'''.replace('__DATA__',data)


def main():
    assert not OUT.exists(),'choose a fresh output folder'
    OUT.mkdir(parents=True)
    assert len([n for n in NODES.values() if n['generation']==0])==4
    for cid,n in NODES.items():
        assert all(NODES[p]['generation']<n['generation'] for p in n['parents'])
        if cid.startswith('M'):assert n['author']==NODES[n['parents'][0]]['author']
        if cid.startswith('X'):assert n['author'] not in [NODES[p]['author'] for p in n['parents']]
    frames=[svg(i/FPS) for i in range(FPS*LENGTH+1)]
    (OUT/'reasonlineage-evolution.html').write_text(html_player(frames))
    (OUT/'lineage.json').write_text(json.dumps({'kind':'conceptual_animation','empirical_model_ranking':False,'models':MODELS,'candidates':NODES,'chapters':CHAPTERS,'seconds':LENGTH,'fps':FPS},ensure_ascii=False,indent=2))
    writer=imageio_ffmpeg.write_frames(str(OUT/'reasonlineage-evolution.mp4'),(1280,720),fps=FPS,codec='libx264',pix_fmt_out='yuv420p',macro_block_size=1,quality=8,output_params=['-movflags','+faststart'],ffmpeg_log_level='error')
    writer.send(None);gif=[]
    for index,frame in enumerate(frames[:-1]):
        png=cairosvg.svg2png(bytestring=frame.encode(),output_width=1280,output_height=720)
        picture=Image.open(io.BytesIO(png)).convert('RGB')
        writer.send(picture.tobytes())
        gif.append(picture.resize((960,540),Image.Resampling.LANCZOS).quantize(colors=96,method=Image.Quantize.FASTOCTREE))
        if index in [0,75,145,190,250,330,374]:picture.save(OUT/f'frame-{index:03d}.png')
        if index%75==0:print(json.dumps({'rendered':index,'total':FPS*LENGTH}),flush=True)
    writer.close()
    durations=[round((i+1)*100/FPS)*10-round(i*100/FPS)*10 for i in range(len(gif))]
    gif[0].save(OUT/'reasonlineage-evolution.gif',save_all=True,append_images=gif[1:],duration=durations,loop=0,optimize=False,disposal=2)
    (OUT/'final-frame.svg').write_text(svg(24))
    shutil_copy=Path(__file__).read_text();(OUT/'build_animation.py').write_text(shutil_copy)
    print(json.dumps({'status':'rendered','frames':len(gif),'duration':sum(durations)/1000,'output':str(OUT)},ensure_ascii=False),flush=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    if args.out:OUT=args.out.resolve()
    main()
