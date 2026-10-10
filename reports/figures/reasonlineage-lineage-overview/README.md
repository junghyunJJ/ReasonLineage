# ReasonLineage — left-to-right lineage overview

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

Left-to-right overview of response evolution in ReasonLineage. Four LLMs produce initial candidate responses. Selected responses are retained across generations (gray connections); mutation refines one parent through its original author (solid teal), and crossover combines two selected parents through another model (dashed gold). Non-author LLM critiques supply fitness for selection. The compact jev layer independently checks structural completeness and provides feedback for newly generated candidates; retained responses keep their existing scores. The final evaluated response and its lineage are preserved. This is an illustrative method diagram, not an empirical model ranking.
