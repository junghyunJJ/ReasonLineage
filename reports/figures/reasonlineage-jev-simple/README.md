# ReasonLineage overview — simple jev footer

jev 하단을 **점검 → 필요할 때 한 번 보완 → 재확인·기록**으로 줄였습니다. 수식, 확률표, Noul·Choice·Score별 상세 판정표는 개요 그림에서 생략했습니다. 평가 알고리즘이나 실행 설정은 바꾸지 않았습니다.

- [그림 PNG](overview.png): 내장 image_gen 편집으로 다듬은 개요.
- [SVG](overview.svg), [고해상도 PNG](overview-native.png): 애니메이션과 같은 데이터와 렌더러, 1664×900 벡터 / 3328×1800 PNG.
- [HTML 애니메이션](animation.html): 재생·정지, 단계 이동, 탐색, 속도, 반복 설정.
- [MP4](animation.mp4): H.264, 1664×900, 15fps, 무음, 28초.
- [GIF](animation.gif): 1248×675, 28초 반복.
- [설명용 계보 데이터](lineage.json), [검증 기록](verification.json), [image_gen 프롬프트](imagegen-prompt.txt).

## Meaning

1. **Check response:** 새 답변에서 요구 요소와 확인된 결함을 점검합니다.
2. **Revise if needed:** 결함이 확인되면 원래 작성자에게 한 번 보완을 요청합니다.
3. **Recheck & record:** 수정본을 다시 점검하고 남은 문제를 기록합니다.

확인된 결함이 없으면 위쪽 우회선을 따라 바로 LLM 동료 평가로 넘어갑니다. 판정이 불명확하면 재확인하거나 검토 필요로 기록하며, 무조건 답변을 다시 쓰게 하지 않습니다. 미해결 표시 자체가 자동 탈락을 뜻하지 않습니다. 첫 애니메이션 점검 장면은 보완 경로, 뒤의 점검 장면은 보완 없는 경로를 설명합니다.

jev는 구조 점검과 피드백을 담당합니다. **선택용 fitness는 작성자를 제외한 LLM들이 계산**합니다. 각 기준의 평가 중앙값을 가중 합성하며, jev 판정값을 fitness에 직접 더하지 않습니다. 보완으로 내용이 바뀌면 이후 동료 평가에 간접 영향을 줄 수 있습니다.

위쪽의 네 모델과 제공사, 자기 평가 제외 표, 생존 답변 두 개, 변이·교차, 계보와 예시 fitness를 유지했습니다. 숫자와 선택 결과는 방법 설명용이며 실제 ALS·AML 측정 결과나 정답 확률이 아닙니다. 이 그림은 네 모델 구성의 개념 개요입니다.

## Suggested caption

**ReasonLineage overview.** Four language models generate initial responses, which are evaluated by the other three models. Two responses survive each selection round and produce one mutation and one crossover offspring. jev checks newly generated responses for structural gaps and may request one revision from the original author, followed by reinspection and recording of unresolved issues. Responses without confirmed gaps proceed directly to peer scoring. Fitness is supplied by non-author LLM reviewers, and retained responses reuse their scores. All displayed fitness values are illustrative.

## Production and verification

Tool mode: built-in `image_gen`, editing the inspected native PNG reference. The original generated file is preserved, and the selected output is copied to overview.png. SVG, native PNG, HTML, GIF, and MP4 use the same deterministic lineage renderer. The GIF/MP4 streams and HTML controller are checked; HTML testing uses a Node VM DOM mock rather than actual browser automation. No research-model or jev evaluation calls were made. Previous figures, experiments, and source references are preserved.
