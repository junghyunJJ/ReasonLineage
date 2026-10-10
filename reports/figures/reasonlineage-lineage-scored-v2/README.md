# ReasonLineage — reviewer exclusion and illustrative fitness

앞단에 자기 평가 제외 표를 추가한 업데이트 버전입니다.

- [최종 PNG](overview.png): 내장 image_gen으로 기존 SVG 그림을 참고해 다듬었습니다.
- [편집용 SVG](overview.svg), [원본 고해상도 PNG](overview-native.png): 애니메이션과 같은 데이터·렌더러.
- [HTML 애니메이션](animation.html): 재생·정지·단계 이동·위치·속도·반복 설정.
- [MP4](animation.mp4): 1664×840, H.264, 15fps, 무음, 28초.
- [GIF](animation.gif): 1248×630, 28초 반복.
- [image_gen 프롬프트](imagegen-prompt.txt), [계보·점수](lineage.json), [검증 기록](verification.json).

## Example scores

| 세대 | 후보와 fitness | 선택 |
|---|---|---|
| G0 | O1 0.62 · S1 0.58 · G1 0.55 · L1 0.49 | O1, S1 |
| G1 | O1 0.62 · S1 0.58 · M1 0.66 · X1 0.64 | M1, X1 |
| G2 | M1 0.66 · X1 0.64 · M2 0.67 · X2 0.70 | X2, M2 |
| G3 | X2 0.70 · M2 0.67 · M3 0.72 · X3 0.71 | 최종 M3 |

모든 숫자는 선택 원리를 설명하기 위한 예시이며 실제 모델 측정값이나 정답 확률이 아닙니다. Opus·GPT·Grok·GLM의 작성자를 제외한 세 모델이 평가하는 4모델 구성도입니다. 기존 3모델 ALS·AML 실행 자료와 구분합니다. 행은 작성자, 열은 평가자이고 대각선 4칸을 제외한 12칸이 평가 가능한 관계입니다. 축별 중앙값을 가중해 fitness를 얻는 개념을 표시했습니다. 개별 평가자 점수는 넣지 않았습니다.

jev 문구는 Check new responses / Separate from fitness scoring으로 변경했습니다. jev는 구조 점검과 피드백을 담당하며 fitness에 판정값을 직접 더하지 않습니다. 재작성으로 답변이 달라지면 이후 LLM 점수에 간접 영향을 줄 수 있습니다. 부모를 그대로 유지하면 점수도 재사용하고, 새 후보 점수는 애니메이션에서 비판·채점 이후에 나타납니다. 생존자는 답변이며 모델을 영구적으로 제외하는 것이 아닙니다.

모든 세대의 선택이 표시 점수와 일치하는지, 자기 평가 제외 표, 유지 점수, GIF·MP4 디코딩과 HTML 제어 로직을 확인했습니다. 실제 브라우저 자동화는 수행하지 않았습니다. 기존 그림·애니메이션·실험 기록은 보존했습니다.

## Suggested caption

Response evolution with self-excluded peer review. Each response is reviewed by the other three models, with criterion-wise median scores combined into a weighted fitness. Illustrative fitness values show why two candidates survive each intermediate generation and why M3 is selected at termination. Gray connections retain responses and their scores, teal connections indicate mutation by the original author, and dashed gold connections indicate crossover by another model. The compact jev layer checks new responses and supplies structural feedback separately from fitness scoring. Scores and model selections are schematic and do not represent empirical performance.
