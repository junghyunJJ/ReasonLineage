"""Add explicit non-author reviewers and illustrative fitness to the approved lineage."""
import html
import importlib.util
import io
import json
import sys
from pathlib import Path

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'pyproject.toml').is_file())
sys.path.insert(0,str(ROOT/'.superpowers/figure-animation-deps'))
import cairosvg
import imageio_ffmpeg
from PIL import Image

OUT=ROOT/'reports/figures/reasonlineage-lineage-scored'
spec=importlib.util.spec_from_file_location('base',ROOT/'.superpowers/figure-animation/build_lineage_overview.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
base.W=1664;base.X=[300,640,980,1320]
SCORES={'O1':.62,'S1':.58,'G1':.55,'L1':.49,'M1':.66,'X1':.64,'M2':.67,'X2':.70,'M3':.72,'X3':.71}
MODELS=list(base.PROVIDERS)
REVIEWERS={author:[judge for judge in MODELS if judge!=author] for author in MODELS}
for cid,value in SCORES.items():base.NODES[cid]['illustrative_fitness']=value
old_svg=base.svg


def peer_panel(t,static):
 p=[base.box(24,190,230,356,'#f8fafc','#d8e2e9')]
 p.append(base.txt(139,220,'Self-excluded review',17,weight=700,anchor='middle'))
 p.append(base.txt(139,243,'Author ↓   Reviewer →',12,'#7a8b97',anchor='middle'))
 names=['Opus','GPT','Grok','GLM'];xx=[102,142,182,222]
 for x,label in zip(xx,names):p.append(base.txt(x,273,label,11.5,'#5d7484',600,'middle'))
 for row,(author,label) in enumerate(zip(MODELS,names)):
  y=302+row*45
  p.append(base.txt(36,y+4,label,13,base.COLORS[author],700))
  active=static or any(c<=t<c+.85 for c in base.CRITIC)
  for col,x in enumerate(xx):
   diagonal=row==col
   p.append(base.box(x-15,y-13,30,27,'#f4eeee' if diagonal else '#e9f5ed' if active else '#f1f4f6','#e4e8ec'))
   if diagonal:
    p.append(f'<path d="M{x-4},{y-4} l8,8 M{x+4},{y-4} l-8,8" stroke="#b47e7e" stroke-width="1.8"/>')
   elif active:
    p.append(f'<path d="M{x-5},{y} l3,3 l7,-7" stroke="#538c6b" stroke-width="2" fill="none"/>')
   else:p.append(base.txt(x,y+3,'·',15,'#a6b3bd',anchor='middle'))
 p.append(base.txt(139,477,'3 reviewers per response',12,'#526c7d',600,'middle'))
 p.append(base.txt(139,501,'Criterion-wise median',11.5,'#7c8d98',anchor='middle'))
 p.append(base.txt(139,522,'→ weighted fitness',11.5,'#7c8d98',anchor='middle'))
 p.append('<path d="M255,372 H284" stroke="#8b9dab" stroke-width="1.8" marker-end="url(#carry)"/>')
 p.append(base.txt(271,358,'fitness',10,'#80919e',anchor='middle'))
 return ''.join(p)


def svg(t=27,static=False):
 s=old_svg(t,static)
 s=s.replace('width="1440" height="840" viewBox="0 0 1440 840"','width="1664" height="840" viewBox="0 0 1664 840"')
 s=s.replace('Responses expand across generations; selection follows non-author LLM critique.',
             'Each response is reviewed by the other three models; example fitness values explain selection.')
 s=s.replace('H720 V716','H942 V716')
 old_jev=(base.box(515,717,410,61,'#dcf5e9' if any(c<=t<c+.85 for c in base.CHECK) and not static else '#f2faf6','#b8d6c6')+
          base.txt(546,745,'jev',21,'#3b745a',700)+base.txt(605,740,'Structural checks & feedback',14,'#557564')+
          base.txt(605,762,'New candidates only · independent of fitness',11,'#789283'))
 new_jev=(base.box(737,717,410,61,'#dcf5e9' if any(c<=t<c+.85 for c in base.CHECK) and not static else '#f2faf6','#b8d6c6')+
          base.txt(768,745,'jev',21,'#3b745a',700)+base.txt(827,740,'Check new responses',14,'#557564')+
          base.txt(827,762,'Separate from fitness scoring',11,'#789283'))
 assert s.count(old_jev)==1
 s=s.replace(old_jev,new_jev)
 s=s.replace('Illustrative lineage · selected colors do not represent empirical model rankings',
             'Illustrative fitness values (0–1) · not empirical model scores or correctness probabilities')
 # Score is reused for carried parents and appears only after critic scoring for new candidates.
 for g,x in enumerate(base.X):
  for row,cid in enumerate(base.POPS[g]):
   alpha=1 if static else base.reveal(t,g,row)
   if alpha<=0:continue
   retained=g>0 and row<2
   available=static or retained or t>=base.CRITIC[g]+.65
   value=f'{SCORES[cid]:.2f}' if available else '—'
   selected=cid in base.SELECTED[g] and (static or t>=base.SELECT[g])
   final=g==3 and cid=='M3' and selected
   color='#316d9e' if final else '#2b6b54' if selected else '#8998a2'
   label=base.txt(x+15,base.Y[row]+76,'fitness '+value,12.5,color,700)
   panel=base.box(x,base.Y[row],base.CW,base.CH,
                  '#eff6ff' if final else '#f2f5f7' if retained else '#ffffff',
                  '#4387c1' if final else '#d2dbe2' if retained or base.NODES[cid]['operator']=='Initial' else base.MUT if base.NODES[cid]['operator']=='Mutation' else base.CROSS,
                  f'stroke-width="{2.5 if final else 1.6}"')
   assert s.count(panel)==1
   s=s.replace(panel,panel+label,1)
 return s.replace('</g></svg>',peer_panel(t,static)+'</g></svg>')


def main():
 assert not OUT.exists(),'output already exists'
 for g,pop in enumerate(base.POPS):
  top=sorted(pop,key=lambda cid:SCORES[cid],reverse=True)[:1 if g==3 else 2]
  assert set(top)==set(base.SELECTED[g])
 assert all(len(j)==3 and author not in j for author,j in REVIEWERS.items())
 OUT.mkdir(parents=True)
 s=svg(static=True);(OUT/'overview.svg').write_text(s)
 png=cairosvg.svg2png(bytestring=s.encode(),output_width=3328,output_height=1680)
 Image.open(io.BytesIO(png)).save(OUT/'overview-native.png',dpi=(300,300))
 spec=importlib.util.spec_from_file_location('player',ROOT/'.superpowers/figure-animation/build_animation.py')
 helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
 helper.CHAPTERS=base.CHAPTERS;helper.FPS=base.FPS;helper.LENGTH=base.LENGTH
 helper.CHAPTERS[2]=(4,'Three non-author reviewers','四모델 중 작성자를 제외한 세 모델이 평가합니다. 예시 fitness가 채점 후 표시됩니다.'.replace('四','네 '))
 frames=[svg(i/base.FPS) for i in range(base.FPS*base.LENGTH+1)]
 player=helper.html_player(frames).replace('max="25"','max="28"')
 player=player.replace('개념 애니메이션 · 4모델 구성','개념 애니메이션 · 설명용 fitness 점수')
 player=player.replace('색상과 선택 결과는 원리를 설명하는 예시이며 실제 모델 순위를 뜻하지 않습니다.',
                       '점수·선택 결과는 설명용 예시이며 실제 모델 순위나 정답 확률을 뜻하지 않습니다.')
 (OUT/'animation.html').write_text(player)
 metadata={'kind':'illustrative_scored_lineage','empirical_scores':False,'reviewers':REVIEWERS,'reviewer_count':3,
           'self_evaluation':False,'illustrative_fitness':SCORES,'nodes':base.NODES,'populations':base.POPS,
           'selected':base.SELECTED,'fps':base.FPS,'duration':base.LENGTH,'jev_text':['Check new responses','Separate from fitness scoring']}
 (OUT/'lineage.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
 writer=imageio_ffmpeg.write_frames(str(OUT/'animation.mp4'),(1664,840),fps=base.FPS,codec='libx264',pix_fmt_out='yuv420p',macro_block_size=1,quality=8,output_params=['-movflags','+faststart'],ffmpeg_log_level='error')
 writer.send(None);gif=[]
 for i,f in enumerate(frames[:-1]):
  data=cairosvg.svg2png(bytestring=f.encode(),output_width=1664,output_height=840)
  picture=Image.open(io.BytesIO(data)).convert('RGB');writer.send(picture.tobytes())
  gif.append(picture.resize((1248,630),Image.Resampling.LANCZOS).quantize(colors=96,method=Image.Quantize.FASTOCTREE))
  if i in [75,130,245,419]:picture.save(OUT/f'frame-{i:03d}.png')
  if i%90==0:print(json.dumps({'rendered':i,'total':420}),flush=True)
 writer.close()
 durations=[round((i+1)*100/base.FPS)*10-round(i*100/base.FPS)*10 for i in range(len(gif))]
 gif[0].save(OUT/'animation.gif',save_all=True,append_images=gif[1:],duration=durations,loop=0,optimize=False,disposal=2)
 (OUT/'build_scored_lineage.py').write_text(Path(__file__).read_text())
 print(json.dumps({'status':'rendered','output':str(OUT),'duration':sum(durations)/1000,'scores':SCORES}),flush=True)


if __name__=='__main__':main()
