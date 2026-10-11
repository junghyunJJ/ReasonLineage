# ReasonLineage overview — compact typed jev checks

간단한 3단계 jev 흐름의 첫 번째 **Check response** 상자 안에 세 판정 타입을 나란히 추가했습니다.

| 타입 | 그림의 표현 | 의미 |
|---|---|---|
| Noul | Present? | 요구된 답변·제안이 있는가? |
| Score | Adequate? | 필수 내용을 충분히 설명했는가? |
| Choice | Priority gap? | 어느 항목을 우선 보완할까? |

세 타입은 한 번의 점검 안에서 독립적으로 요청되는 판정입니다. Noul → Score → Choice 순서로 실행하는 세 단계라는 뜻은 아닙니다. 이 판정들을 현재의 결함 확인 정책에 따라 함께 사용해 보완 여부와 대상을 결정합니다. Score는 구조·내용 충실도 점검이며, 모델들이 계산하는 선택용 fitness와 구분됩니다.

흐름은 **점검 → 필요하면 같은 작성자가 한 번 보완 → 재확인·기록**입니다. 확인된 결함이 없으면 바로 LLM 동료 평가로 넘어갑니다. 불명확한 판정은 재확인하거나 기록하고, 보완 후 남은 문제도 기록합니다. 표시가 남았다는 이유만으로 자동 탈락시키는 흐름은 아닙니다.

- [그림 PNG](overview.png): 내장 image_gen으로 다듬은 개요.
- [SVG](overview.svg), [고해상도 PNG](overview-native.png): 애니메이션과 같은 계보 데이터와 렌더러.
- [HTML 애니메이션](animation.html): 재생·정지, 단계 이동, 탐색, 속도·반복 설정.
- [MP4](animation.mp4): 1664×900, H.264, 15fps, 무음, 28초.
- [GIF](animation.gif): 1248×675, 42초 반복 (HTML·MP4보다 1.5배 느림).
- [계보 데이터](lineage.json), [검증 기록](verification.json), [제작 프롬프트](imagegen-prompt.txt).

## Suggested caption

**ReasonLineage overview.** Four language models generate initial responses, each evaluated by the other three models. Two responses survive selection and produce one mutation and one crossover offspring. jev inspects new responses using parallel typed assessments: Noul for answer presence, Score for adequacy of required content, and Choice for the priority gap. Confirmed defects may trigger one revision by the original author, followed by reinspection and recording. Responses without confirmed gaps proceed directly to peer scoring. Fitness comes from non-author LLM reviewers. All displayed fitness values are illustrative.

## Production and scope

Tool mode: built-in image_gen editing the inspected native PNG reference, using the linked prompt. Previous figures and experiment records are preserved. The four-model layout and numbers illustrate the method; these are not measured ALS·AML results or correctness probabilities. No jev or research-model API evaluations were run for this visual change. Native SVG and animation share the same renderer. HTML controller verification uses a Node VM DOM mock, not browser automation; media streams are separately decoded and checked.
