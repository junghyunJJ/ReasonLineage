"""Explain typed jev outputs and the real composition policy beneath the lineage."""
import html
import importlib.util
import io
import json
import sys
from pathlib import Path

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'pyproject.toml').is_file())
sys.path.insert(0,str(ROOT/'.superpowers/figure-animation-deps'))
sys.path.insert(0,str(ROOT/'src'))
import cairosvg
import imageio_ffmpeg
from PIL import Image
from reasonlineage.checks.base import CheckAnswer
from reasonlineage.checks.combined import verdict

OUT=ROOT/'reports/figures/reasonlineage-jev-explained'
spec=importlib.util.spec_from_file_location('scored',ROOT/'.superpowers/figure-animation/build_scored_lineage.py')
scored=importlib.util.module_from_spec(spec);spec.loader.exec_module(scored)
base=scored.base;base.H=1024
J1=json.loads((ROOT/'research/co-scientist-pilot/protocol-jev-combined/protocol.json').read_text())['j1']
BEFORE={'presence':.96,'gap':'validation','gap_p':.78,'levels':[.10,.70,.15,.05]}
AFTER={'presence':.99,'gap':'none','gap_p':.95,'levels':[.02,.08,.30,.60]}
CHOICE_BEFORE={'validation':.78,'mechanism':.08,'premises':.06,'falsifier':.04,'uncertain':.02,'none':.01,'no_proposal':.01}
CHOICE_AFTER={'none':.95,'validation':.01,'mechanism':.01,'premises':.01,'falsifier':.01,'uncertain':.01,'no_proposal':0}


def answers(data):
 a={'proposal_present':{'probabilities':{'yes':data['presence'],'no':1-data['presence']}},
    'primary_gap':{'probabilities':CHOICE_BEFORE if data['gap']=='validation' else CHOICE_AFTER}}
 for name,spec in J1['components'].items():
  probabilities=data['levels'] if name=='validation' else [0,.10,.20,.70]
  a[spec['question']]={'probabilities':{str(k):p for k,p in enumerate(probabilities)}}
 return a


def stats(data):
 p={str(k):v for k,v in enumerate(data['levels'])}
 return CheckAnswer('score',p).value,data['levels'][2]+data['levels'][3]


def demonstration(t,static):
 if static:return BEFORE
 checks=[c for c in base.CHECK if c<=t]
 if not checks:return BEFORE
 return BEFORE if t<checks[-1]+.4 else AFTER


def footer(t,static):
 data=demonstration(t,static);mean,adequacy=stats(data);good=data['gap']=='none'
 p=[base.box(24,692,1616,259,'#fbfdfb','#d8e7de')]
 p.append(base.txt(44,717,'jev · Typed structural checks',21,'#386d54',700))
 p.append(base.txt(394,715,'Check new responses · Separate from fitness scoring',13,'#6d8779'))
 p.append(base.txt(1058,715,'Parallel probability outputs → conditional rules',12,'#87998e'))
 # Three typed judgments are parallel outputs, not a probability product.
 p.append('<path d="M196,835 H202 V737 H904" fill="none" stroke="#b8cbbf" stroke-width="1.2"/>')
 for cx in [322,568,904]:p.append(f'<path d="M{cx},737 V751" stroke="#b8cbbf" stroke-width="1.2" fill="none"/>')
 p.append('<path d="M322,919 V929 H1114 V830 H1120 M568,919 V929 M904,919 V929" fill="none" stroke="#b8cbbf" stroke-width="1.2"/>')
 for x,w in [(32,164),(208,228),(448,240),(700,408),(1120,512)]:
  p.append(base.box(x,754,w,163,'#ffffff','#dce7e0'))
 p.append(base.txt(48,778,'Input',17,'#456655',700))
 for y,line in [(806,'Response text'),(829,'+ task-specific'),(849,'questions'),(881,'→ typed'),(901,'probabilities')]:
  p.append(base.txt(48,y,line,12.5,'#7a8d80'))
 p.append(base.txt(224,778,'Noul · Presence',17,'#456655',700))
 p.append(base.txt(224,802,'Substantive response?',13,'#6f8578'))
 p.append(base.txt(224,833,f'P(yes) = {data["presence"]:.2f}',20,'#4f8968',700))
 p.append(base.txt(224,855,f'P(no) = {1-data["presence"]:.2f}',12,'#8b9b90'))
 p.append(base.txt(224,903,'P(yes) < 0.5 → full rewrite',11.5,'#6d8375'))
 p.append(base.txt(464,778,'Choice · Priority',17,'#456655',700))
 p.append(base.txt(464,802,'Which structural gap first?',12.5,'#6f8578'))
 gap='no gap' if good else data['gap']
 p.append(base.txt(464,833,gap,20,'#5b9474' if good else '#b39352',700))
 p.append(base.txt(464,855,f'P(top category) = {data["gap_p"]:.2f}',12,'#8b9b90'))
 p.append(base.box(464,865,208,6,'#edf2ef','#edf2ef'))
 p.append(base.box(464,865,208*data['gap_p'],6,'#90b69e' if good else '#d3bc82','#90b69e' if good else '#d3bc82'))
 p.append(base.txt(464,886,f'Other categories: {1-data["gap_p"]:.2f}',11,'#8b9b90'))
 p.append(base.txt(464,903,'argmax P(gap) → first priority',11.5,'#6d8375'))
 p.append(base.txt(716,778,'Score · Per task criterion',17,'#456655',700))
 p.append(base.txt(716,800,'Example: validation completeness',12,'#6f8578'))
 labels=['0 absent','1 vague','2 adequate','3 clear']
 for k,(value,label) in enumerate(zip(data['levels'],labels)):
  cx=758+k*90
  p.append(base.txt(cx,815,f'{value:.2f}',11,'#7b9083',anchor='middle'))
  height=value*45
  p.append(f'<rect x="{cx-23}" y="{853-height}" width="46" height="{height}" rx="2" fill="{"#d7a1a9" if k<2 else "#87b09b"}"/>')
  p.append(base.txt(cx,868,label,10,'#8a9a8f',anchor='middle'))
 p.append(base.txt(716,888,f'Mean = sum k·P(k) = {mean:.2f} (out of 3; record)',11.2,'#7b8f81'))
 symbol='≥' if adequacy>=.5 else '<'
 p.append(base.txt(716,907,f'P(adequate) = P(2)+P(3) = {adequacy:.2f} {symbol} 0.50',11.8,'#538a69' if good else '#b28b54',700))
 p.append(base.txt(1136,778,'Conditional rules → feedback',17,'#456655',700))
 rules=[(801,'P(yes) < 0.5: rewrite the whole response'),
        (822,'Choice agrees with weak Score: targeted rewrite'),
        (843,'Mismatch: recheck once; unresolved → flag'),
        (864,'Same author: at most 1 rewrite → recheck'),
        (885,'All adequate + no gap: pass'),
        (906,'Residual gaps are recorded; no rewrite loop')]
 for y,line in rules:p.append(base.txt(1136,y,line,12,'#6d8375'))
 if not static and good:example='Example recheck: validation adequacy 0.90 → pass (other required parts assumed adequate)'
 else:example='Illustrative check: validation adequacy 0.20 → one same-author revision → recheck 0.90 (pass)'
 p.append(base.txt(832,938,example,12,'#779183',600,'middle'))
 return ''.join(p)


def svg(t=27,static=False):
 s=scored.svg(t,static)
 s=s.replace('width="1664" height="840" viewBox="0 0 1664 840"','width="1664" height="1024" viewBox="0 0 1664 1024"')
 small=(base.box(737,717,410,61,'#dcf5e9' if any(c<=t<c+.85 for c in base.CHECK) and not static else '#f2faf6','#b8d6c6')+
        base.txt(768,745,'jev',21,'#3b745a',700)+base.txt(827,740,'Check new responses',14,'#557564')+
        base.txt(827,762,'Separate from fitness scoring',11,'#789283'))
 assert s.count(small)==1
 s=s.replace(small,'').replace('H942 V716','H942 V692')
 for xx,color,label,dashed in [(114,base.CARRY,'Retain',False),(417,base.MUT,'Mutation',False),(762,base.CROSS,'Crossover',True)]:
  old=f'<path d="M{xx},802 h56" stroke="{color}" stroke-width="2.5" {"stroke-dasharray=\"7 5\"" if dashed else ""}/>'
  s=s.replace(old,old.replace(',802',',974'))
  s=s.replace(base.txt(xx+66,807,label,14,'#627482'),base.txt(xx+66,979,label,14,'#627482'))
 s=s.replace(base.txt(1093,807,'LLM critics → fitness → selection',13,'#73818b'),
             base.txt(1093,979,'LLM critics → fitness → selection',13,'#73818b'))
 old_note=base.txt(base.W/2,829,'Illustrative fitness values (0–1) · not empirical model scores or correctness probabilities',11,'#95a1aa',anchor='middle')
 new_note=base.txt(832,1012,'Illustrative fitness and jev probabilities · structural judgments are not factual correctness estimates',11,'#95a1aa',anchor='middle')
 assert s.count(old_note)==1
 return s.replace(old_note,new_note).replace('</g></svg>',footer(t,static)+'</g></svg>')


def main():
 assert not OUT.exists(),'output exists'
 before=verdict(answers(BEFORE),J1);after=verdict(answers(AFTER),J1)
 assert before['would_rewrite'] and before['focus']==['validation'] and not before['needs_review']
 assert not after['would_rewrite'] and not after['needs_review']
 assert abs(stats(BEFORE)[0]-1.15)<1e-10 and abs(stats(BEFORE)[1]-.20)<1e-10
 assert abs(stats(AFTER)[0]-2.48)<1e-10 and abs(stats(AFTER)[1]-.90)<1e-10
 OUT.mkdir(parents=True)
 static=svg(static=True);(OUT/'overview.svg').write_text(static)
 png=cairosvg.svg2png(bytestring=static.encode(),output_width=3328,output_height=2048)
 Image.open(io.BytesIO(png)).save(OUT/'overview-native.png',dpi=(300,300))
 spec=importlib.util.spec_from_file_location('player',ROOT/'.superpowers/figure-animation/build_animation.py')
 helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
 helper.CHAPTERS=base.CHAPTERS;helper.FPS=15;helper.LENGTH=28
 for index,g in [(1,0),(6,1),(11,2),(16,3)]:
  helper.CHAPTERS[index]=(base.CHECK[g],'jev: probabilities → feedback','jev가 Noul·Choice·Score 확률을 반환합니다. 예시 충분 확률 0.20은 보완 후 재점검에서 0.90으로 바뀝니다.')
 frames=[svg(i/15) for i in range(421)]
 player=helper.html_player(frames).replace('max="25"','max="28"')
 player=player.replace('개념 애니메이션 · 4모델 구성','개념 애니메이션 · jev 판정과 설명용 점수')
 player=player.replace('색상과 선택 결과는 원리를 설명하는 예시이며 실제 모델 순위를 뜻하지 않습니다.',
                       'fitness와 jev 확률은 설명용 예시입니다. jev 평균 점수는 기록하고, 보완 여부는 충분할 확률과 조건부 규칙으로 판단합니다.')
 (OUT/'animation.html').write_text(player)
 meta={'kind':'illustrative_jev_typed_evaluation','empirical_data':False,'illustrative_fitness':scored.SCORES,
       'reviewers':scored.REVIEWERS,'populations':base.POPS,'selected':base.SELECTED,'nodes':base.NODES,
       'before':BEFORE,'after':AFTER,'before_mean':stats(BEFORE)[0],'after_mean':stats(AFTER)[0],
       'before_adequacy':stats(BEFORE)[1],'after_adequacy':stats(AFTER)[1],
       'before_decision':before,'after_decision':after,'thresholds':J1['thresholds'],
       'probability_source':'jev returns distributions; local code computes expected level and adequacy',
       'composition':'conditional rules, not averages/products across question types','fps':15,'duration':28}
 (OUT/'explanation.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
 writer=imageio_ffmpeg.write_frames(str(OUT/'animation.mp4'),(1664,1024),fps=15,codec='libx264',pix_fmt_out='yuv420p',macro_block_size=1,quality=8,output_params=['-movflags','+faststart'],ffmpeg_log_level='error')
 writer.send(None);gif=[]
 for i,f in enumerate(frames[:-1]):
  picture=Image.open(io.BytesIO(cairosvg.svg2png(bytestring=f.encode(),output_width=1664,output_height=1024))).convert('RGB')
  writer.send(picture.tobytes())
  gif.append(picture.resize((1248,768),Image.Resampling.LANCZOS).quantize(colors=96,method=Image.Quantize.FASTOCTREE))
  if i in [45,55,75,140,419]:picture.save(OUT/f'frame-{i:03d}.png')
  if i%90==0:print(json.dumps({'rendered':i,'total':420}),flush=True)
 writer.close()
 durations=[round((i+1)*100/15)*10-round(i*100/15)*10 for i in range(len(gif))]
 gif[0].save(OUT/'animation.gif',save_all=True,append_images=gif[1:],duration=durations,loop=0,optimize=False,disposal=2)
 (OUT/'build_jev_detail.py').write_text(Path(__file__).read_text())
 print(json.dumps({'status':'rendered','seconds':sum(durations)/1000,'mean':stats(BEFORE)[0],'adequacy':stats(BEFORE)[1],'output':str(OUT)}),flush=True)


if __name__=='__main__':main()
