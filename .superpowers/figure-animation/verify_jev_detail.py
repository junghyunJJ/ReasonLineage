import copy
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
sys.path.insert(0,str(ROOT/'src'))
import imageio_ffmpeg
from PIL import Image,ImageSequence
from reasonlineage.checks.combined import verdict

OUT=ROOT/'reports/figures/reasonlineage-jev-explained'
spec=importlib.util.spec_from_file_location('detail',ROOT/'.superpowers/figure-animation/build_jev_detail.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
for data in [mod.BEFORE,mod.AFTER]:
 assert abs(sum(data['levels'])-1)<1e-12
 assert 0<=data['presence']<=1
for p in [mod.CHOICE_BEFORE,mod.CHOICE_AFTER]:assert abs(sum(p.values())-1)<1e-12
assert abs(mod.stats(mod.BEFORE)[0]-1.15)<1e-12 and abs(mod.stats(mod.BEFORE)[1]-.2)<1e-12
assert abs(mod.stats(mod.AFTER)[0]-2.48)<1e-12 and abs(mod.stats(mod.AFTER)[1]-.9)<1e-12
before=verdict(mod.answers(mod.BEFORE),mod.J1);after=verdict(mod.answers(mod.AFTER),mod.J1)
assert before['would_rewrite'] and before['focus']==['validation'] and not before['needs_review']
assert not after['would_rewrite'] and not after['needs_review']
absent=copy.deepcopy(mod.AFTER);absent['presence']=.2
assert verdict(mod.answers(absent),mod.J1)['focus']==['proposal']
mismatch=mod.answers(mod.BEFORE);mismatch['primary_gap']['probabilities']=mod.CHOICE_AFTER
conflict=verdict(mismatch,mod.J1)
assert conflict['needs_review'] and not conflict['would_rewrite']
boundary=copy.deepcopy(mod.AFTER);boundary['presence']=.5;boundary['levels']=[0,.5,.5,0]
assert not verdict(mod.answers(boundary),mod.J1)['would_rewrite']
for g,pop in enumerate(mod.base.POPS):
 assert set(sorted(pop,key=lambda cid:mod.scored.SCORES[cid],reverse=True)[:1 if g==3 else 2])==set(mod.base.SELECTED[g])
for t in [0,3,3.5,9,9.5,21,21.5,27.9]:ET.fromstring(mod.svg(t))
assert (OUT/'overview.svg').read_text()==mod.svg(static=True)
assert '1.15 (out of 3; record)' in mod.svg(3) and '2.48 (out of 3; record)' in mod.svg(3.5)
assert '0.20 &lt; 0.50' in mod.svg(3) and '0.90 ≥ 0.50' in mod.svg(3.5)
assert Image.open(OUT/'overview-native.png').size==(3328,2048)
assert Image.open(OUT/'overview.png').width>1400
gif=Image.open(OUT/'animation.gif');assert gif.size==(1248,768) and gif.info['loop']==0
duration=count=0
for frame in ImageSequence.Iterator(gif):duration+=frame.info.get('duration',0);count+=1
assert duration==28000 and count>100
reader=imageio_ffmpeg.read_frames(str(OUT/'animation.mp4'));meta=next(reader);decoded=sum(1 for _ in reader)
assert tuple(meta['size'])==(1664,1024) and decoded==420 and meta['fps']==15
result=subprocess.run(['node',str(ROOT/'.superpowers/figure-animation/verify_lineage_player.js'),str(OUT/'animation.html')],capture_output=True,text=True,cwd=ROOT)
assert result.returncode==0,'player verification failed'
controller=json.loads(result.stdout)
for src,name in [('build_scored_lineage.py','scored_renderer.py'),('build_lineage_overview.py','lineage_renderer.py'),('build_animation.py','player_helper.py'),('verify_jev_detail.py','verify_jev_detail.py'),('verify_lineage_player.js','verify_player.js')]:
 shutil.copyfile(ROOT/'.superpowers/figure-animation'/src,OUT/name)
report={'status':'passed','score_mean_before':1.15,'score_mean_after':2.48,'adequacy_before':.20,'adequacy_after':.90,
        'actual_conditional_policy_verified':True,'tested_cases':['matching defect','repaired pass','absent response','choice/score mismatch','threshold equality'],
        'fitness_examples_preserved':True,'static_png_mode':'built-in image_gen; labels and arithmetic visually inspected',
        'native_png':[3328,2048],'gif':{'size':[1248,768],'frames':count,'seconds':duration/1000},
        'mp4':{'size':list(meta['size']),'frames':decoded,'fps':meta['fps'],'seconds':meta.get('duration'),'codec':meta.get('codec')},
        'player':controller,'research_llm_calls':0,'jev_service_calls':0,'imagegen_calls':1,'illustrative_probabilities':True}
(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
readme='''# ReasonLineage — jev evaluation explained

하단에 jev의 입력, 세 판정 타입, 점수 계산, 조건부 보완 규칙을 추가했습니다. 위쪽 계보·자기 평가 제외 표·예시 fitness는 유지했습니다.

- [PNG](overview.png): 내장 image_gen으로 다듬은 그림.
- [SVG](overview.svg), [고해상도 PNG](overview-native.png): 애니메이션과 같은 데이터·렌더러.
- [HTML 애니메이션](animation.html): 재생/정지, 단계 이동, 위치·속도·반복 설정.
- [MP4](animation.mp4): 1664×1024, H.264, 15fps, 무음, 28초.
- [GIF](animation.gif): 1248×768, 28초 반복.
- [설명용 데이터](explanation.json), [검증 기록](verification.json), [image_gen 프롬프트](imagegen-prompt.txt).

## How the score is calculated

jev에 답변과 과제에 맞게 정의한 질문을 전달하면 타입별 확률이 반환됩니다. Noul은 P(yes), Choice는 선택지별 확률, Score는 기준별 단계 확률을 반환합니다. 그림은 이 반환값을 우리 코드에서 활용하는 과정을 설명하며, jev 내부 신경망이나 확률 생성 알고리즘을 새로 주장하지 않습니다.

Score 예시는 P(0,1,2,3)=(0.10,0.70,0.15,0.05)입니다. 단계는 없음·모호함·충분함·명확함입니다.

- 평균 점수: 0×0.10 + 1×0.70 + 2×0.15 + 3×0.05 = **1.15점**, 0–3 척도입니다. 이 값은 기록합니다.
- 재작성 판단용 충분 확률: P(2)+P(3)=**0.20**, 임계값 0.5 미만이므로 해당 항목은 부족합니다.
- 평균 점수를 3으로 나눈 값을 임계값에 비교하지 않습니다. 서로 다른 타입의 확률을 곱하거나 평균해 공동 성공 확률을 만들지도 않습니다.

Noul P(yes)=0.96이면 답변이 있다는 판정입니다. Choice에서 validation이 0.78로 가장 높고 해당 Score도 부족하므로, 원래 작성자에게 그 부분을 한 번 보완하도록 요청합니다. Choice에는 0.5 임계값을 적용하지 않고 최대 확률의 항목을 우선 대상으로 삼습니다.

보완 후 예시는 P(0,1,2,3)=(0.02,0.08,0.30,0.60)으로, 평균 2.48점·충분 확률 0.90입니다. 다른 필수 항목도 충분하고 Choice가 none을 선택하면 통과합니다. 애니메이션에서 점검 시점에 이 전후 변화를 보여줍니다. 이 구조 예시는 특정 계보 카드의 실제 판정 결과가 아닙니다.

## Decision rules

1. Noul P(yes)<0.5이면 전체 답변 재작성.
2. 가설/답변이 존재하고 Choice의 우선 결함과 부족한 Score가 일치하면 해당 항목 중심 재작성.
3. 판정 불일치는 같은 본문으로 jev 한 번 재확인. 계속 불일치하면 검토 필요로 기록.
4. 작성자 재작성은 최대 한 번. 수정본 재검사 후에도 결함이 남으면 기록하며 자동 재작성 루프를 만들지 않습니다.
5. 모든 항목이 충분하고 우선 결함이 none이면 통과.

현재 생의학 J1 프로필에는 Noul 1문항·Choice 1문항·Score 4문항(기전, 근거/추측 구분, 검증 전략, 반증 관찰)이 있습니다. 그림의 Score는 그중 검증 전략 한 항목의 예시이며, 다른 세 항목은 충분하다고 가정했습니다. 범용 개요에서는 질문·기준을 과제에 맞게 정의합니다.

Jev의 구조 판정값은 선택용 fitness에 직접 합산되지 않습니다. 재작성으로 내용이 달라지면 이후 LLM 비판 점수에 간접 영향을 줄 수 있습니다. 숫자는 모두 설명용이며 실제 모델 측정값이나 현실의 정답 확률이 아닙니다. 생존자는 답변이고 모델을 영구적으로 제외하는 선택이 아닙니다.

## Verification and provenance

확률 합계·기대 점수·충분 확률과 현재 combined.verdict의 재작성·통과·불일치·경계 판정을 실제 코드로 확인했습니다. GIF/MP4를 디코딩하고 HTML 제어 로직을 검증했습니다. 실제 브라우저 자동화는 수행하지 않았습니다. 실제 LLM/jev 평가 호출은 없고 그림 제작용 image_gen 호출만 한 번 수행했습니다. 기존 그림·애니메이션·실험 기록은 보존했습니다.

구현 근거: src/reasonlineage/checks/base.py, combined.py, gate.py. Criteria의 사실성·인용 정확성을 보장한다는 주장은 없습니다.
'''
(OUT/'README.md').write_text(readme)
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='sha256-manifest.json'}
(OUT/'sha256-manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(report,ensure_ascii=False))
