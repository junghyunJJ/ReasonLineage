# ALS·AML jev on/off 전체 실험

2026-10-09 실행 완료. **원본 13개 완료 + 실패 후 별도 보완 3개로, 16개 조건의 최종 결과를 모두 확보했다.** 원본 상태는 [pair-status.json](pair-status.json)에 보존한다. 전체 최종 결과는 [completed-summary.json](completed-summary.json), 설명은 [비교 보고서](../../reports/2026-10-09-jev-controlled.md), 전체 가설·점수·비판은 [진화 뷰어](evolution-viewer.html)에서 볼 수 있다. 고정된 계획은 [pair-plan.json](pair-plan.json)에 기록한다.

| 조건 | 과제 | 구성 |
|---|---|---|
| jev on | ALS·AML | 다중 모델·GPT 단독·Grok 단독·GLM Flash 단독 |
| jev off | ALS·AML | 같은 네 구성 |

GPT·Grok·GLM-5.3-Flash만 사용한다. 두 군 모두 DeepSeek·Opus·Laya가 없다. 질문·문헌 패킷·모델·effort·프롬프트·요청seed·초기3·생존2·3진화세대·두 비판을 유지한다. 다중 모델 후속 후보는 변이1+교차1, 단독은 같은 모델의 변이2다.

on은 jev J1의 Noul1·Choice1·Score4 판단에 따라 같은 작성자에게 후보별 최대1회 수정을 요청하며, 판정 불일치는 jev로1회 재확인한다. J2는 기록용이다. off는 J1/J2를 호출하지 않는다.

실행 순서는 on8→off8이다. 각 군4시간·각 슬롯45분/모델40회/800000보고토큰 상한을 유지한다. on에는 슬롯별 jev70회 상한이 추가된다. 전체 계획의1208호출은 예약을 포함한 최대값이며 실제사용량이 아니다.

## 읽을 기록

- `jev-on/`·`jev-off/`: 각 군의 `frozen-inputs`, `study.json`, 사용량과 익명 전문가 자료. 집계 파일은 해당 군 종료 후 생긴다.
- 각 `runs/als-reasonlineage` 등의 `events.jsonl`: 가설 생성·비판·채점·선택·부모 관계.
- 각 슬롯의 `calls/`: 공개 입력과 답변. on의 재작성도 별도 호출로 남긴다.
- on의 `checks.jsonl`·`checker-calls.jsonl`·`diagnostics/`: jev 분포·초점·재확인·잔여 결함·진단.
- 종료 후 `comparison.json`·`report.md`: 8개의 on/off 비교 쌍, 초기·최종 fitness, 실제 사용량과 완료/부분 상태.
- 종료 후 `paired-review-materials/expert`: 두 군을 합쳐 익명화한 전문가용 가설. 군·작성자·단계 매핑은 `analyst`에 분리한다. 아직 전문가 평가 결과가 아니다.

동일한 요청seed가 같은 답변을 보장하지는 않는다. 조건별 단 한 번이므로 통계적 유의성이나 jev의 일반적 인과효과를 입증하지 않는다. 순차 실행 순서와 추가 수정/검사 비용을 함께 고려한다. 내부 fitness와 구조 충실도는 과학적 사실성·실험 성공률과 구분한다. 문헌 주장 확인과 전문가 평가는 별도 미완료 항목이다.

기존 실험은 덮어쓰지 않는다. 실패·시간 종료·부분검사도 결과에서 제외하지 않는다.

## 완료 후 확인

총 144개 가설·288개 비판을 기록했다. ON의 J1 72개가 모두 통과해 jev 재작성은 0회였다. J2 216개도 진단 기록으로 보존했다. ON/OFF 점수 차이를 jev 수정 효과로 해석하지 않는다.

보완은 `terminal-completions`(누락 평가만), `planned-step-completions`(GLM 첫 보완 실패), `structured-completions`(GLM 원래 예정된 마지막 가설·평가 완료)에 구분했다. 새로운 세대나 예정 외 가설은 추가하지 않았다. 원본 실패는 정상 완료로 덮어쓰지 않았다.

전문가용 최종 익명 자료는 `completed-review-materials/expert`에 있다. 실제 전문가 평가와 개별 인용 주장 검증은 아직 수행되지 않았다. 기존 `paired-review-materials`는 원본 완료분만 포함하며 그대로 보존했다.
