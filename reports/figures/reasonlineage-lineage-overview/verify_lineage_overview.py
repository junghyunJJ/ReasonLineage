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

OUT=ROOT/'reports/figures/reasonlineage-lineage-overview'
spec=importlib.util.spec_from_file_location('lineage',ROOT/'.superpowers/figure-animation/build_lineage_overview.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
assert len(mod.NODES)==10 and sum(len(p) for p in mod.POPS)==16
for g,population in enumerate(mod.POPS):
 assert len(population)==4 and set(mod.SELECTED[g]).issubset(population)
 assert mod.CHECK[g]<mod.CRITIC[g]<mod.SELECT[g]
 if g:
  assert population[:2]==mod.SELECTED[g-1]
  assert all(mod.NODES[c]['generation']==g for c in population[2:])
for cid,n in mod.NODES.items():
 assert all(mod.NODES[p]['generation']<n['generation'] for p in n['parents'])
 if n['operator']=='Mutation':assert len(n['parents'])==1 and n['author']==mod.NODES[n['parents'][0]]['author']
 if n['operator']=='Crossover':assert len(n['parents'])==2 and n['author'] not in [mod.NODES[p]['author'] for p in n['parents']]
assert mod.SELECTED[-1]==['M3']
for t in [0,2.9,6.4,8.9,14.9,20.9,27.9]:ET.fromstring(mod.svg(t))
ET.fromstring((OUT/'overview.svg').read_text())
assert (OUT/'overview.svg').read_text()==mod.svg(static=True)
assert 'Saved score' in mod.svg(8.9) and 'Final response' in mod.svg(27.9)
assert Image.open(OUT/'overview.png').size==(2880,1680)
gif=Image.open(OUT/'animation.gif');assert gif.size==(1080,630) and gif.info['loop']==0
duration=count=0
for frame in ImageSequence.Iterator(gif):duration+=frame.info.get('duration',0);count+=1
assert duration==28000 and count>100
reader=imageio_ffmpeg.read_frames(str(OUT/'animation.mp4'));meta=next(reader);decoded=sum(1 for _ in reader)
assert tuple(meta['size'])==(1440,840) and meta['fps']==15 and decoded==420
result=subprocess.run(['node',str(ROOT/'.superpowers/figure-animation/verify_lineage_player.js'),str(OUT/'animation.html')],capture_output=True,text=True,cwd=ROOT)
assert result.returncode==0,'HTML controller verification failed'
controller=json.loads(result.stdout)
for name in ['verify_lineage_player.js','verify_lineage_overview.py']:
 shutil.copyfile(ROOT/'.superpowers/figure-animation'/name,OUT/name)
shutil.copyfile(ROOT/'.superpowers/figure-animation/build_animation.py',OUT/'player_helper.py')
report={'status':'passed','kind':'conceptual_method_overview','layout':'left-to-right G0/G1/G2/G3; small jev below',
        'unique_responses':10,'displayed_candidate_instances':16,'parent_connections':15,'source_svg_frames':421,
        'static_png':[2880,1680],'gif':{'dimensions':[1080,630],'encoded_frames':count,'duration_seconds':duration/1000,'loop':True},
        'mp4':{'dimensions':list(meta['size']),'decoded_frames':decoded,'fps':meta['fps'],'codec':meta.get('codec'),'duration_seconds':meta.get('duration')},
        'player':controller,'mutation_author_inherits_parent':True,'crossover_author_excludes_parent_authors':True,
        'jev_before_critique_before_selection':True,'retained_candidates_keep_saved_scores':True,
        'source_image_modified':False,'model_calls':0,'uses_actual_model_scores':False}
(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
caption='Left-to-right overview of response evolution in ReasonLineage. Four LLMs produce initial candidate responses. Selected responses are retained across generations (gray connections); mutation refines one parent through its original author (solid teal), and crossover combines two selected parents through another model (dashed gold). Non-author LLM critiques supply fitness for selection. The compact jev layer independently checks structural completeness and provides feedback for newly generated candidates; retained responses keep their existing scores. The final evaluated response and its lineage are preserved. This is an illustrative method diagram, not an empirical model ranking.'
(OUT/'README.md').write_text('''# ReasonLineage — left-to-right lineage overview

참고 스크린샷처럼 G0→G1→G2→G3 계보가 오른쪽으로 펼쳐집니다. jev는 아래쪽의 작은 점검 레이어입니다. 그림과 애니메이션은 같은 SVG 렌더러와 계보 데이터를 사용합니다.

- [그림 PNG](overview.png): 2880×1680, 300dpi.
- [편집·확대용 SVG](overview.svg).
- [HTML 애니메이션](animation.html): 자동 재생, 재생/정지, 단계 이동, 위치·속도·반복 설정. 동작 줄이기 설정이 켜진 환경은 정지 상태로 시작합니다.
- [MP4](animation.mp4): 1440×840, H.264, 15fps, 무음, 28초.
- [GIF](animation.gif): 1080×630, 28초 반복.
- [계보·단계](lineage.json), [검증 기록](verification.json).

회색 선은 유지, 청록 실선은 변이, 노란 점선은 교차입니다. 생존자는 답변이며 모델을 영구적으로 제외하는 선택이 아닙니다. 초기 4개, 이후 생존 2개+변이 1개+교차 1개입니다. jev는 새 후보를 점검하며 선택용 fitness는 LLM 비판으로 계산합니다. 숫자 점수는 넣지 않았고 모델 선택 결과는 원리를 설명하는 예시입니다. 실제 모델 순위나 4모델 실험 성과를 주장하지 않습니다. 기존 그림·애니메이션·실험 자료·참고 스크린샷은 수정하지 않았습니다.

SVG 장면과 PNG를 시각 확인하고 GIF/MP4를 디코딩했습니다. HTML 제어 로직을 Node에서 검증했으며 실제 브라우저 자동화는 수행하지 않았습니다. 원본 생성 코드는 build_lineage_overview.py, HTML 플레이어 참조는 player_helper.py에 있습니다. 렌더링 의존성은 프로젝트 .superpowers/figure-animation-deps에 격리 설치했습니다.

## Suggested caption

'''+caption+'\n')
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file()}
(OUT/'sha256-manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(report,ensure_ascii=False))
