# jev on/off ALS·AML 전체 비교

조건별 한 번의 탐색적 실행이다. jev가 없는 군에서도 DeepSeek를 사용하지 않는다. 
동일한 질문·모델·프롬프트·seed·진화조건을 사용하되, 공급자 응답의 결정성은 보장하지 않는다. 
순차 실행 순서와 추가 검사/수정 비용도 차이의 해석에 고려해야 한다.

전체 생성 완료: 13/16. J1/J2까지 확인된 비교 쌍: 5/8.

| 과제 | 구성 | jev on 상태 | off 상태 | on 최종 | off 최종 | on−off | 검사까지 확인 |
|---|---|---|---|---:|---:|---:|---|
| ALS | reasonlineage | completed | completed | 0.8355 | 0.8420 | -0.0065 | 예 |
| ALS | gpt | failed | completed | — | 0.8735 | — | 아니오 |
| ALS | grok | completed | completed | 0.8215 | 0.7965 | 0.0250 | 예 |
| ALS | glm | completed | failed | 0.8615 | — | — | 아니오 |
| AML | reasonlineage | completed | completed | 0.8210 | 0.8175 | 0.0035 | 예 |
| AML | gpt | completed | completed | 0.8730 | 0.8585 | 0.0145 | 예 |
| AML | grok | failed | completed | — | 0.7915 | — | 아니오 |
| AML | glm | completed | completed | 0.8380 | 0.8155 | 0.0225 | 예 |

점수는 실행 내부 비판 모델의 fitness이며 과학적 사실성·실험 성공률을 뜻하지 않는다.
문헌 주장 확인과 전문가의 내용 평가는 별도이며 아직 완료되지 않았다.

## 실제 사용량

| 조건 | 총 호출 | 보고 토큰 | 사용량 미확인 호출 |
|---|---:|---:|---:|
| jev-on | 451 | 3371711 | 3 |
| jev-off | 212 | 2915203 | 1 |

기록 폴더: `runs/jev-controlled-2026-10-09`. 각 슬롯의 `events.jsonl`, `calls/`, `status.json`에 전체 진화·공개 프롬프트·응답을 저장했다.
jev on에는 `checks.jsonl`, `checker-calls.jsonl`, `diagnostics/`가 추가된다. off는 checker를 호출하지 않는다.
실패·부분검사·미시작도 그대로 포함하며 정상완료로 바꾸지 않는다. 기존 실험 결과는 보존한다.
