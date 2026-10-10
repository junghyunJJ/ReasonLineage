import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'pyproject.toml').is_file())
sys.path.insert(0,str(ROOT/'.superpowers/figure-animation-deps'))
import imageio_ffmpeg
from PIL import Image,ImageSequence

OUT=ROOT/'reports/figures/reasonlineage-animation-v2'
spec=importlib.util.spec_from_file_location('animation',ROOT/'.superpowers/figure-animation/build_animation.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
def visible(t):return {r['id']:r for r in mod.scene(t)[0] if r['opacity']>.5}
assert set(visible(2.9))=={'A0','B0','C0','D0'}
assert set(visible(7.9))=={'A0','B0'}
assert set(visible(11.9))=={'A0','B0','M1','X1'}
before=visible(11.9);after=visible(13.6)
for cid in ['A0','B0']:
    assert (before[cid]['x'],before[cid]['y'])==(after[cid]['x'],after[cid]['y'])
for cid in ['M1','X1']:
    assert (before[cid]['x'],before[cid]['y'])!=(after[cid]['x'],after[cid]['y'])
assert set(visible(15.9))=={'M1','X1'}
assert set(visible(19.9))=={'M1','X1','M2','X2'}
assert set(visible(24))=={'M2'}
image=Image.open(OUT/'reasonlineage-evolution.gif')
assert image.size==(960,540) and image.info['loop']==0
duration=0;count=0
for frame in ImageSequence.Iterator(image):duration+=frame.info.get('duration',0);count+=1
assert duration==25000 and count>100
reader=imageio_ffmpeg.read_frames(str(OUT/'reasonlineage-evolution.mp4'))
meta=next(reader);decoded=sum(1 for _ in reader)
assert tuple(meta['size'])==(1280,720) and meta['fps']==15 and decoded==375
result=subprocess.run(['node',str(ROOT/'.superpowers/figure-animation/verify_player.js'),str(OUT/'reasonlineage-evolution.html')],cwd=ROOT,capture_output=True,text=True)
assert result.returncode==0,'player controller validation failed'
controls=json.loads(result.stdout)
shutil.copyfile(ROOT/'.superpowers/figure-animation/verify_player.js',OUT/'verify_player.js')
shutil.copyfile(Path(__file__),OUT/'verify_exports.py')
shutil.copyfile(OUT/'frame-145.png',OUT/'poster.png')
report={'status':'passed','kind':'conceptual_animation','source_svg_frames':376,
        'gif':{'dimensions':[960,540],'encoded_frames':count,'duration_seconds':duration/1000,'infinite_loop':True},
        'mp4':{'dimensions':list(meta['size']),'fps':meta['fps'],'decoded_frames':decoded,'codec':meta.get('codec'),'duration_seconds':meta.get('duration')},
        'player':controls,'lineage':'initial4/select2/mutation1/crossover1/retain2/new2/reevaluate-new-only/2generations/final-response verified',
        'actual_model_calls':0,'uses_empirical_model_scores':False,'source_bitmap_modified':False,
        'verification_images':['frame-075.png','frame-145.png','frame-374.png']}
(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
(OUT/'README.md').write_text('''# ReasonLineage evolution animation

25초 개념 애니메이션입니다. 기존 Overview의 네 모델·jev 구조 점검·LLM 채점·선택·변이·교차를 SVG로 새로 구성했습니다. 기존 PNG와 실험 결과를 수정하지 않았으며 모델 호출을 수행하지 않았습니다.

- [HTML 재생](reasonlineage-evolution.html): 브라우저에서 열면 자동 재생됩니다. 재생/정지, 이전/다음 단계, 재생 위치, 속도, 반복 설정을 지원합니다. 동작 줄이기 설정이 켜진 환경에서는 정지 상태로 시작합니다.
- [GIF](reasonlineage-evolution.gif): 960×540, 25초 무한 반복.
- [MP4](reasonlineage-evolution.mp4): 1280×720, H.264, 15fps, 무음. 발표 자료에 삽입할 수 있습니다.
- [미리보기](poster.png), [최종 SVG](final-frame.svg), [계보·단계](lineage.json), [검증 기록](verification.json).

초기 4개 후보에서 부모 2개를 선택하고 변이 1개·교차 1개를 추가합니다. 새 후보만 다시 평가하며 부모의 점수는 유지합니다. G1·G2의 두 번 반복은 원리를 설명하는 예시입니다. 모델 선택 결과와 색상은 실제 성능 순위가 아닙니다. jev는 구조 점검과 피드백을 담당하며 선택용 fitness는 LLM 비판으로 계산합니다.

HTML은 외부 이미지·폰트·서버에 의존하지 않는 한 파일입니다. SVG 렌더와 내보낸 GIF/MP4를 확인했고 HTML 제어 로직을 Node에서 검증했습니다. 실제 브라우저 자동화 검사는 수행하지 않았습니다.

## Rebuild

프로젝트 루트에서 `python .superpowers/figure-animation/build_animation.py --out reports/figures/reasonlineage-animation-new`를 실행합니다. 이미 있는 출력 폴더는 덮어쓰지 않습니다. 렌더링 패키지는 `.superpowers/figure-animation-deps`에 격리 설치했습니다. 필요한 Python 패키지는 CairoSVG, imageio-ffmpeg, Pillow입니다. 생성 스크립트 사본은 이 폴더의 build_animation.py에 있습니다.
''')
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file()}
(OUT/'sha256-manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(report,ensure_ascii=False))
