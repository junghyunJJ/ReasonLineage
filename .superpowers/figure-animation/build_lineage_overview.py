"""One deterministic left-to-right lineage layout for static and animated figures."""
import hashlib
import html
import importlib.util
import io
import json
import math
import sys
from pathlib import Path

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'pyproject.toml').is_file())
sys.path.insert(0,str(ROOT/'.superpowers/figure-animation-deps'))
import cairosvg
import imageio_ffmpeg
from PIL import Image

OUT=ROOT/'reports/figures/reasonlineage-lineage-overview'
FPS,LENGTH=15,28
W,H=1440,840
X=[40,384,728,1072];Y=[190,300,410,520];CW,CH=264,86
MUT,CROSS,CARRY='#179d91','#c99525','#9ba9b6'
COLORS={'Opus 5.5':'#e9925d','GPT-6.1 sol':'#659be5','Grok 4.7':'#a17ad6','GLM-5.3-flash':'#df759a'}
PROVIDERS={'Opus 5.5':'Anthropic','GPT-6.1 sol':'OpenAI','Grok 4.7':'xAI','GLM-5.3-flash':'Z.ai'}
NODES={
 'O1':{'author':'Opus 5.5','parents':[],'operator':'Initial','generation':0},
 'S1':{'author':'GPT-6.1 sol','parents':[],'operator':'Initial','generation':0},
 'G1':{'author':'Grok 4.7','parents':[],'operator':'Initial','generation':0},
 'L1':{'author':'GLM-5.3-flash','parents':[],'operator':'Initial','generation':0},
 'M1':{'author':'Opus 5.5','parents':['O1'],'operator':'Mutation','generation':1},
 'X1':{'author':'Grok 4.7','parents':['O1','S1'],'operator':'Crossover','generation':1},
 'M2':{'author':'Opus 5.5','parents':['M1'],'operator':'Mutation','generation':2},
 'X2':{'author':'GPT-6.1 sol','parents':['M1','X1'],'operator':'Crossover','generation':2},
 'M3':{'author':'GPT-6.1 sol','parents':['X2'],'operator':'Mutation','generation':3},
 'X3':{'author':'Grok 4.7','parents':['X2','M2'],'operator':'Crossover','generation':3},
}
POPS=[['O1','S1','G1','L1'],['O1','S1','M1','X1'],['M1','X1','M2','X2'],['X2','M2','M3','X3']]
SELECTED=[['O1','S1'],['M1','X1'],['X2','M2'],['M3']]
CHECK=[3,9,15,21];CRITIC=[4,10,16,22];SELECT=[5,11,17,23]
CHAPTERS=[
 (0,'Initial responses','네 모델이 각각 초기 답변을 만듭니다.'),
 (3,'jev · structural checks','아래쪽의 jev가 초기 후보의 구조와 요구 요소를 점검합니다.'),
 (4,'LLM critique','작성자를 제외한 LLM 비판으로 fitness를 계산합니다.'),
 (5,'Select two parents','두 답변을 선택하고 다른 후보는 흐리게 표시합니다.'),
 (6,'Retain parents','회색 선은 선택된 답변을 다음 세대로 유지하는 경로입니다.'),
 (7,'Mutation & crossover','청록 선은 한 부모의 변이, 노란 점선은 두 부모의 교차입니다.'),
 (9,'jev · new candidates','새로 생성된 두 후보만 jev가 점검합니다.'),
 (10,'LLM critique','새 후보의 LLM 비판·채점이 진행됩니다. 부모의 기존 점수는 유지합니다.'),
 (11,'Select next parents','이번 개념 예시에서는 새 후보 두 개를 다음 부모로 선택합니다.'),
 (12,'Retain parents','선택된 계보가 오른쪽 세대로 이어집니다.'),
 (13,'Mutation & crossover','동일한 작성자는 변이를, 다른 모델은 교차를 수행합니다.'),
 (15,'jev · new candidates','하단 jev가 새 후보 두 개를 점검합니다.'),
 (16,'LLM critique','작성자를 제외한 비판 모델이 새 후보를 채점합니다.'),
 (17,'Select next parents','다음 변이를 수행할 부모와 교차 부모 두 개를 선택합니다.'),
 (18,'Retain parents','부모 답변이 마지막 표시 세대로 전달됩니다.'),
 (19,'Mutation & crossover','부모와 자식의 연결을 보존하며 새로운 답변을 만듭니다.'),
 (21,'jev · new candidates','마지막 새 후보의 구조 점검을 수행합니다.'),
 (22,'LLM critique','최종 선택 전 LLM 비판·채점을 마칩니다.'),
 (23,'Final response','평가를 마친 후보에서 최종 답변 하나를 선택합니다.'),
 (24,'Complete lineage','초기 답변부터 최종 답변까지 계보가 남습니다. 실제 모델 순위가 아닌 개념 예시입니다.'),
]


def smooth(v):
 v=max(0,min(1,v));return v*v*(3-2*v)


def txt(x,y,s,size=15,color='#24384b',weight=400,anchor='start'):
 return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" font-weight="{weight}" fill="{color}">{html.escape(str(s))}</text>'


def box(x,y,w,h,fill,stroke,extra=''):
 return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" {extra}/>'


def born(g,row):
 return .3+row*.35 if g==0 else 6*g+(0 if row<2 else 1)+(row%2)*.35


def reveal(t,g,row):
 return smooth((t-born(g,row))/.95)


def curve(g,parent,child):
 r0=POPS[g-1].index(parent);r1=POPS[g].index(child)
 x0=X[g-1]+CW;x1=X[g];y0=Y[r0]+CH/2;y1=Y[r1]+CH/2
 pts=[]
 for i in range(65):
  v=i/64;u=1-v
  pts.append((u**3*x0+3*u*u*v*(x0+43)+3*u*v*v*(x1-43)+v**3*x1,
              u**3*y0+3*u*u*v*y0+3*u*v*v*y1+v**3*y1))
 length=sum(math.hypot(b[0]-a[0],b[1]-a[1]) for a,b in zip(pts,pts[1:]))
 return f'M{x0},{y0} C{x0+43},{y0} {x1-43},{y1} {x1},{y1}',length


def svg(t=27,static=False):
 p=['<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="840" viewBox="0 0 1440 840"><defs>']
 for name,color in [('carry',CARRY),('mut',MUT),('cross',CROSS)]:
  p.append(f'<marker id="{name}" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7" fill="{color}"/></marker>')
 p.append('</defs><g font-family="DejaVu Sans, sans-serif">'+box(0,0,W,H,'#ffffff','#ffffff'))
 p.append(txt(W/2,48,'ReasonLineage · Response evolution',31,weight=700,anchor='middle'))
 p.append(txt(W/2,78,'Responses expand across generations; selection follows non-author LLM critique.',15,'#6d7e8b',anchor='middle'))
 current=0 if t<6 else min(3,int(t//6))
 for g,x in enumerate(X):
  p.append(box(x-8,109,CW+16,512,'#fafbfc','#e6ebef'))
  label=['G0 · Initial responses','G1','G2','G3 · Final selection'][g]
  p.append(txt(x+CW/2,141,label,20,'#263e50' if static or g==current else '#85939e',700,'middle'))
  p.append(txt(x+CW/2,166,'4 candidates' if g==0 else '2 retained + 2 offspring',12,'#89959e',anchor='middle'))
 # Inter-generation connections appear from the parent toward the child.
 for g in range(1,4):
  for row,cid in enumerate(POPS[g]):
   n=NODES[cid];retained=row<2
   parents=[cid] if retained else n['parents']
   name='carry' if retained else 'mut' if n['operator']=='Mutation' else 'cross'
   color={'carry':CARRY,'mut':MUT,'cross':CROSS}[name]
   progress=1 if static else smooth((t-born(g,row))/.85)
   if progress<=0:continue
   for parent in parents:
    d,length=curve(g,parent,cid)
    if name=='cross':
     visible=f'MASK{g}{row}{parent}'
     p.append(f'<defs><mask id="{visible}" maskUnits="userSpaceOnUse"><path d="{d}" fill="none" stroke="white" stroke-width="10" stroke-dasharray="{length:.3f}" stroke-dashoffset="{length*(1-progress):.3f}"/></mask></defs>')
     p.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.5" stroke-dasharray="7 5" mask="url(#{visible})"/>')
    else:
     p.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{1.7 if retained else 2.5}" stroke-dasharray="{length:.3f}" stroke-dashoffset="{length*(1-progress):.3f}"/>')
    if progress>.96:p.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-opacity=".01" marker-end="url(#{name})"/>')
 # Small inspection layer, separate from generational fitness/selection.
 pulse=next((g for g,c in enumerate(CHECK) if c<=t<c+.85),None) if not static else None
 for g,x in enumerate(X):
  on=static or t>=CHECK[g]
  if on:
   color=MUT if pulse==g else '#c7d3cf'
   p.append(f'<path d="M{x+CW/2},626 V686 H720 V716" stroke="{color}" stroke-width="{2 if pulse==g else 1.1}" stroke-dasharray="3 5" fill="none"/>')
   p.append(f'<circle cx="{x+CW/2}" cy="626" r="3" fill="{color}"/>')
 for g,x in enumerate(X):
  for row,cid in enumerate(POPS[g]):
   alpha=1 if static else reveal(t,g,row)
   if alpha<=0:continue
   n=NODES[cid];selected=cid in SELECTED[g];ranked=static or t>=SELECT[g]
   retained=g>0 and row<2;final=g==3 and cid=='M3' and ranked
   eliminated=ranked and not selected and g<3
   color=COLORS[n['author']]
   stroke='#d2dbe2' if retained or n['operator']=='Initial' else MUT if n['operator']=='Mutation' else CROSS
   fill='#ffffff' if not retained else '#f2f5f7'
   if final:stroke='#4387c1';fill='#eff6ff'
   textcolor='#7d8c97' if eliminated else '#253e50'
   y=Y[row]
   p.append(f'<g opacity="{alpha:.3f}">')
   p.append(box(x,y,CW,CH,fill,stroke,f'stroke-width="{2.5 if final else 1.6}"'))
   p.append(f'<circle cx="{x+17}" cy="{y+24}" r="5.5" fill="{color}" opacity="{.5 if eliminated else 1}"/>')
   heading=f'{cid} · Retained' if retained else f'{cid} · {n["author"]}'
   p.append(txt(x+30,y+30,heading,15.5,textcolor,700))
   if retained:detail=n['author']
   elif g==0:detail=PROVIDERS[n['author']]
   else:detail=n['operator']+' of '+' + '.join(n['parents'])
   p.append(txt(x+15,y+53,detail,13,'#768795' if retained or g==0 else stroke))
   if retained and not ranked:status='Saved score'
   elif not ranked:status='Awaiting check' if t<CHECK[g] else 'Checked' if t<CRITIC[g] else 'Critic scoring'
   elif final:status='Final response'
   elif g==3:status='Evaluated'
   else:status='Selected' if selected else 'Discarded'
   if status in ['Selected','Final response']:
    tw=105 if final else 78
    p.append(box(x+CW-tw-12,y+62,tw,18,'#e6f4ed' if not final else '#dbeafa','#e6f4ed' if not final else '#dbeafa'))
    p.append(txt(x+CW-tw/2-12,y+75,status,10.5,'#33775d' if not final else '#31699e',600,'middle'))
   else:p.append(txt(x+CW-12,y+75,status,10.5,'#8b99a4',anchor='end'))
   p.append('</g>')
 # Legend: the evolutionary graph takes priority; jev is a compact support layer.
 for xx,color,label,dashed in [(114,CARRY,'Retain',False),(417,MUT,'Mutation',False),(762,CROSS,'Crossover',True)]:
  p.append(f'<path d="M{xx},802 h56" stroke="{color}" stroke-width="2.5" {"stroke-dasharray=\"7 5\"" if dashed else ""}/>')
  p.append(txt(xx+66,807,label,14,'#627482'))
 p.append(txt(1093,807,'LLM critics → fitness → selection',13,'#73818b'))
 fill='#dcf5e9' if pulse is not None else '#f2faf6'
 p.append(box(515,717,410,61,fill,'#b8d6c6'))
 p.append(txt(546,745,'jev',21,'#3b745a',700))
 p.append(txt(605,740,'Structural checks & feedback',14,'#557564'))
 p.append(txt(605,762,'New candidates only · independent of fitness',11,'#789283'))
 p.append(txt(W/2,829,'Illustrative lineage · selected colors do not represent empirical model rankings',11,'#95a1aa',anchor='middle'))
 p.append('</g></svg>');return ''.join(p)


def main():
 assert not OUT.exists(),'output folder already exists'
 OUT.mkdir(parents=True)
 static=svg(static=True)
 (OUT/'overview.svg').write_text(static)
 png=cairosvg.svg2png(bytestring=static.encode(),output_width=2880,output_height=1680)
 Image.open(io.BytesIO(png)).save(OUT/'overview.png',dpi=(300,300))
 spec=importlib.util.spec_from_file_location('player',ROOT/'.superpowers/figure-animation/build_animation.py')
 helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
 helper.FPS=FPS;helper.LENGTH=LENGTH;helper.CHAPTERS=CHAPTERS
 frames=[svg(i/FPS) for i in range(FPS*LENGTH+1)]
 player=helper.html_player(frames).replace('max="25"','max="28"')
 player=player.replace('새 후보만 다시 평가하며 부모는 기존 점수를 유지합니다.','왼쪽에서 오른쪽으로 계보가 확장됩니다. 새 후보만 점검·채점하며 부모는 기존 점수를 유지합니다.')
 (OUT/'animation.html').write_text(player)
 metadata={'kind':'conceptual_lineage','empirical_model_scores':False,'fps':FPS,'duration':LENGTH,'models':PROVIDERS,'nodes':NODES,'populations':POPS,'selected':SELECTED,'chapters':CHAPTERS,'jev':'structural checks only; fitness from LLM critics','static_and_animation':'same SVG renderer'}
 (OUT/'lineage.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
 writer=imageio_ffmpeg.write_frames(str(OUT/'animation.mp4'),(W,H),fps=FPS,codec='libx264',pix_fmt_out='yuv420p',macro_block_size=1,quality=8,output_params=['-movflags','+faststart'],ffmpeg_log_level='error')
 writer.send(None);gif=[]
 for i,s in enumerate(frames[:-1]):
  png=cairosvg.svg2png(bytestring=s.encode(),output_width=W,output_height=H)
  image=Image.open(io.BytesIO(png)).convert('RGB');writer.send(image.tobytes())
  gif.append(image.resize((1080,630),Image.Resampling.LANCZOS).quantize(colors=96,method=Image.Quantize.FASTOCTREE))
  if i in [44,130,224,328,385,419]:image.save(OUT/f'frame-{i:03d}.png')
  if i%90==0:print(json.dumps({'rendered':i,'total':FPS*LENGTH}),flush=True)
 writer.close()
 durations=[round((i+1)*100/FPS)*10-round(i*100/FPS)*10 for i in range(len(gif))]
 gif[0].save(OUT/'animation.gif',save_all=True,append_images=gif[1:],duration=durations,loop=0,optimize=False,disposal=2)
 (OUT/'build_lineage_overview.py').write_text(Path(__file__).read_text())
 print(json.dumps({'status':'rendered','frames':len(gif),'seconds':sum(durations)/1000,'output':str(OUT)},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
