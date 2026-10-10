import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'pyproject.toml').is_file())
sys.path.insert(0,str(ROOT/'.superpowers/figure-animation-deps'))
import imageio_ffmpeg
from PIL import Image,ImageSequence
OUT=ROOT/'reports/figures/reasonlineage-lineage-scored-v2'
spec=importlib.util.spec_from_file_location('scored',ROOT/'.superpowers/figure-animation/build_scored_lineage.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
assert mod.OUT==OUT
for author,reviewers in mod.REVIEWERS.items():
 assert author not in reviewers and len(reviewers)==3 and len(set(reviewers))==3
for g,population in enumerate(mod.base.POPS):
 ordered=sorted(population,key=lambda cid:mod.SCORES[cid],reverse=True)
 assert set(ordered[:1 if g==3 else 2])==set(mod.base.SELECTED[g])
 if g:assert population[:2]==mod.base.SELECTED[g-1]
 if g:
  best_parent=max(mod.base.SELECTED[g-1],key=lambda cid:mod.SCORES[cid])
  assert mod.base.NODES[f'M{g}']['parents']==[best_parent]
  assert set(mod.base.NODES[f'X{g}']['parents'])==set(mod.base.SELECTED[g-1])
for cid,node in mod.base.NODES.items():
 assert node['illustrative_fitness']==mod.SCORES[cid]
 if node['operator']=='Mutation':assert node['author']==mod.base.NODES[node['parents'][0]]['author']
 if node['operator']=='Crossover':assert node['author'] not in [mod.base.NODES[p]['author'] for p in node['parents']]
panel=ET.fromstring('<svg>'+mod.peer_panel(27,True)+'</svg>')
crosses=[p for p in panel.iter('path') if p.attrib.get('stroke')=='#b47e7e']
checks=[p for p in panel.iter('path') if p.attrib.get('stroke')=='#538c6b']
assert len(crosses)==4 and len(checks)==12
assert mod.svg(27,True)==(OUT/'overview.svg').read_text()
assert 'New candidates only' not in mod.svg(27,True) and 'independent of fitness' not in mod.svg(27,True)
assert 'Check new responses' in mod.svg(27,True) and 'Separate from fitness scoring' in mod.svg(27,True)
assert 'fitness —' in mod.svg(3.5) and 'fitness 0.62' in mod.svg(5)
assert 'Saved score' in mod.svg(8.9) and 'fitness 0.62' in mod.svg(8.9)
assert mod.SCORES['M3']==.72 and mod.SCORES['X3']==.71
assert Image.open(OUT/'overview-native.png').size==(3328,1680)
assert Image.open(OUT/'overview.png').width>1500
gif=Image.open(OUT/'animation.gif');assert gif.size==(1248,630) and gif.info['loop']==0
duration=count=0
for frame in ImageSequence.Iterator(gif):duration+=frame.info.get('duration',0);count+=1
assert duration==28000 and count>100
reader=imageio_ffmpeg.read_frames(str(OUT/'animation.mp4'));meta=next(reader);decoded=sum(1 for _ in reader)
assert tuple(meta['size'])==(1664,840) and meta['fps']==15 and decoded==420
result=subprocess.run(['node',str(ROOT/'.superpowers/figure-animation/verify_lineage_player.js'),str(OUT/'animation.html')],capture_output=True,text=True,cwd=ROOT)
assert result.returncode==0,'HTML player validation failed'
controller=json.loads(result.stdout)
for source,name in [('build_lineage_overview.py','lineage_renderer.py'),('build_animation.py','player_helper.py'),('verify_lineage_player.js','verify_player.js'),('verify_scored_lineage.py','verify_scored_lineage.py')]:
 shutil.copyfile(ROOT/'.superpowers/figure-animation'/source,OUT/name)
report={'status':'passed','initial_author_count':4,'reviewers_per_candidate':3,'self_review_cells_excluded':4,
        'eligible_peer_review_cells':12,'illustrative_fitness':mod.SCORES,'all_selections_follow_displayed_fitness':True,
        'retained_scores_reused':True,'final_response':'M3','final_fitness':.72,
        'jev_text':['Check new responses','Separate from fitness scoring'],
        'static_png_mode':'built-in image_gen; visually checked against the canonical SVG and scores',
        'native_svg_and_animation':'same validated data','native_png_dimensions':[3328,1680],
        'gif':{'dimensions':[1248,630],'frames':count,'seconds':duration/1000,'loop':True},
        'mp4':{'dimensions':list(meta['size']),'frames':decoded,'fps':meta['fps'],'seconds':meta.get('duration'),'codec':meta.get('codec')},
        'player':controller,'empirical_scores':False,'research_llm_calls':0,'imagegen_calls':1}
(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
lines=['# ReasonLineage — reviewer exclusion and illustrative fitness','',
       '앞단에 자기 평가 제외 표를 추가한 업데이트 버전입니다.','',
       '- [최종 PNG](overview.png): 내장 image_gen으로 기존 SVG 그림을 참고해 다듬었습니다.',
       '- [편집용 SVG](overview.svg), [원본 고해상도 PNG](overview-native.png): 애니메이션과 같은 데이터·렌더러.',
       '- [HTML 애니메이션](animation.html): 재생·정지·단계 이동·위치·속도·반복 설정.',
       '- [MP4](animation.mp4): 1664×840, H.264, 15fps, 무음, 28초.',
       '- [GIF](animation.gif): 1248×630, 28초 반복.',
       '- [image_gen 프롬프트](imagegen-prompt.txt), [계보·점수](lineage.json), [검증 기록](verification.json).','',
       '## Example scores','',
       '| 세대 | 후보와 fitness | 선택 |','|---|---|---|',
       '| G0 | O1 0.62 · S1 0.58 · G1 0.55 · L1 0.49 | O1, S1 |',
       '| G1 | O1 0.62 · S1 0.58 · M1 0.66 · X1 0.64 | M1, X1 |',
       '| G2 | M1 0.66 · X1 0.64 · M2 0.67 · X2 0.70 | X2, M2 |',
       '| G3 | X2 0.70 · M2 0.67 · M3 0.72 · X3 0.71 | 최종 M3 |','',
       '모든 숫자는 선택 원리를 설명하기 위한 예시이며 실제 모델 측정값이나 정답 확률이 아닙니다. Opus·GPT·Grok·GLM의 작성자를 제외한 세 모델이 평가하는 4모델 구성도입니다. 기존 3모델 ALS·AML 실행 자료와 구분합니다. 행은 작성자, 열은 평가자이고 대각선 4칸을 제외한 12칸이 평가 가능한 관계입니다. 축별 중앙값을 가중해 fitness를 얻는 개념을 표시했습니다. 개별 평가자 점수는 넣지 않았습니다.','',
       'jev 문구는 Check new responses / Separate from fitness scoring으로 변경했습니다. jev는 구조 점검과 피드백을 담당하며 fitness에 판정값을 직접 더하지 않습니다. 재작성으로 답변이 달라지면 이후 LLM 점수에 간접 영향을 줄 수 있습니다. 부모를 그대로 유지하면 점수도 재사용하고, 새 후보 점수는 애니메이션에서 비판·채점 이후에 나타납니다. 생존자는 답변이며 모델을 영구적으로 제외하는 것이 아닙니다.','',
       '모든 세대의 선택이 표시 점수와 일치하는지, 자기 평가 제외 표, 유지 점수, GIF·MP4 디코딩과 HTML 제어 로직을 확인했습니다. 실제 브라우저 자동화는 수행하지 않았습니다. 기존 그림·애니메이션·실험 기록은 보존했습니다.','',
       '## Suggested caption','',
       'Response evolution with self-excluded peer review. Each response is reviewed by the other three models, with criterion-wise median scores combined into a weighted fitness. Illustrative fitness values show why two candidates survive each intermediate generation and why M3 is selected at termination. Gray connections retain responses and their scores, teal connections indicate mutation by the original author, and dashed gold connections indicate crossover by another model. The compact jev layer checks new responses and supplies structural feedback separately from fitness scoring. Scores and model selections are schematic and do not represent empirical performance.','']
(OUT/'README.md').write_text('\n'.join(lines))
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='sha256-manifest.json'}
(OUT/'sha256-manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(report,ensure_ascii=False))
