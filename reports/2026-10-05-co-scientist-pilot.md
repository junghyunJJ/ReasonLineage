# Co-Scientist pilot 결과

완료된 실행은 0/10개다. 따라서 ReasonLineage의 우위를 판단할 수 없다. 사용자 승인에 따라 초기·중간 참고 가설 14개를 별도로 평가했고, 독립 LLM 평가 4회가 완료됐다. 전문가의 참고 평가는 대기 중이다. 실패·상한 중단은 가설 품질 점수로 바꾸지 않았다.

코드 고정: `29c0da040c1a882ac7f01701f32647323f28cf0b`. 오프라인 검증: 686 passed, 3 live deselected. GLM: `glm-5.3-flash`, 독립 평가: `deepseek-v4.1-flash`.

| 과제 | 방법 | 상태 | 요청 시도 | 보고 토큰 | 사용량 미확인 호출 | 초기 내부 점수 | 최종 내부 점수 |
|---|---|---|---:|---:|---:|---:|---:|
| ALS | reasonlineage | failed | 4 | 0 | 4 | — | — |
| AML | reasonlineage | failed | 4 | 0 | 4 | — | — |
| ALS | gpt | 시간 상한 중단 | 24 | 243,822 | 1 | 0.863 | — |
| AML | gpt | 시간 상한 중단 | 26 | 252,243 | 2 | 0.857 | — |
| ALS | opus | failed | 2 | 0 | 2 | — | — |
| AML | opus | failed | 2 | 0 | 2 | — | — |
| ALS | grok | failed | 18 | 232,461 | 1 | 0.771 | — |
| AML | grok | failed | 4 | 67,323 | 0 | — | — |
| ALS | glm | failed | 18 | 132,586 | 1 | 0.848 | — |
| AML | glm | failed | 18 | 144,530 | 0 | 0.835 | — |

표의 점수는 내부 선택용 fitness다. 독립 LLM 평가나 전문가 판정과 같지 않다. 보고 토큰이 0인 실패 호출의 실제 소비량은 미확인이다.

전체 요청 시도 124회, 보고 토큰 1,136,954, 사용량 미확인 17회. 실제 청구 비용은 확인 불가다.

## 실패 및 중단 사유

- ALS / reasonlineage: write c001 by opus failed: g0/write/c001/opus failed after 1 attempt(s): ['backend exit 1']
- AML / reasonlineage: write c001 by opus failed: g0/write/c001/opus failed after 1 attempt(s): ['backend exit 1']
- ALS / gpt: judge gpt-r2 on c006 failed: g1/judge/c006/gpt-r2 failed after 1 attempt(s): ['model timeout at remaining budget']
- AML / gpt: mutate c007 by gpt failed: g2/mutate/c007/gpt failed after 1 attempt(s): ['model timeout at remaining budget']
- ALS / opus: write c002 by opus failed: g0/write/c002/opus failed after 1 attempt(s): ['backend exit 1']
- AML / opus: write c002 by opus failed: g0/write/c002/opus failed after 1 attempt(s): ['backend exit 1']
- ALS / grok: mutate c006 by grok failed: proposal outside the agreed 400–800 word range
- AML / grok: write c004 by grok failed: proposal outside the agreed 400–800 word range
- ALS / glm: mutate c005 by glm failed: proposal outside the agreed 400–800 word range
- AML / glm: mutate c005 by glm failed: proposal outside the agreed 400–800 word range

## 독립 평가와 사용량 비교

독립 평가의 순서 정방향·역방향은 순서 편향 점검이며, 독립 표본 수를 늘리지 않는다.

- ALS / forward: unstarted
- ALS / reverse: unstarted
- AML / forward: unstarted
- AML / reverse: unstarted

최종 완료 답이 없어 원래 최종 비교용 LLM 평가는 시작하지 않았다. 대신 승인받은 참고 가설 자료에 평가 예산 4회를 사용했다. 초기 내부 1위(없으면 ID순 첫 유효 초안)와 가장 최근 수정 세대의 공개 응답 전부를 포함했다. 길이 조건을 넘긴 수정본도 참고용으로 보존했으며, 정식 완료 답으로 바꾸지 않았다.

- 참고 평가 ALS / forward: completed
- 참고 평가 ALS / reverse: completed
- 참고 평가 AML / forward: completed
- 참고 평가 AML / reverse: completed

ALS 참고 가설의 독립 근거성 평점은 2–3/5, AML은 3–4/5였다. 순서에 따라 일부 평점이 달라졌으며 두 순서 결과를 독립 표본으로 세지 않는다. 높은 구체성·검증 가능성 점수는 생물학적 사실의 확인을 뜻하지 않는다. Grok 수정본이 가정한 NUP62 Ser59/84/178/221은 사람 표준 서열의 L/G/N/L과 맞지 않았다. 모델 평가도 이 위치를 근거 없는 가정으로 지적했지만, 표준 서열 불일치까지 확인하지는 못했다.


계획한 8개 다중 모델–단독 모델 비교 중 사용량 비교 기준을 충족한 것은 0개다. 완료 여부, 누락 없는 사용량, 총토큰 비율 0.9–1.1을 함께 요구한다. 실제 FLOPs를 측정하지 않았다.

## 자료

- [전문가용 익명 참고 평가 ZIP](evidence/2026-10-05-co-scientist-pilot/expert-only.zip): 이 ZIP만 전문가에게 먼저 전달한다. 방법·단계 대응표와 자동 평가·문헌 검증 결론은 포함하지 않는다.
- [전체 상태·요약](evidence/2026-10-05-co-scientist-pilot/study.json)
- [공개 계보 CSV](evidence/2026-10-05-co-scientist-pilot/evolution.csv)
- [공개 가설과 비판](evidence/2026-10-05-co-scientist-pilot/public-candidates/)
- [문헌 검증](evidence/2026-10-05-co-scientist-pilot/literature-verification.md)

전문가에게는 익명 평점과 과제별 전체 선호순위를 받는다. 비교쌍 연결 구조가 다중 모델 답을 드러내므로, 계획한 비교는 분석 측에서 순위로부터 도출한다. 직접 쌍별 선호 질문과 평가 맥락이 다르며 첫 실제 호출 전에 수정·고정했다.

사용량 누락은 이후 토큰 예산이 있는 호출을 중단시킨다. 모든 필수 응답이 이미 완료된 경우 유효한 답은 보존하되 사용량 비교에서 제외한다. 문헌 확인은 주장 검증의 범위를 명시하며 실제 생물학적 효과·신규 발견을 입증하지 않는다.
