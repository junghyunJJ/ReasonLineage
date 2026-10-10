# 3단계 A 진행 기록 (2026-10-04)

설계: `specs/2026-10-04-gold-weather-level3-design.md` (사전 등록 `673d46a`). 브랜치 `gold-weather-l3`.

## 커밋
- `673d46a` 사전 등록 (설계 문서)
- `32d6769` `compare_conditions`, `change_verdict(alpha)` + 테스트
- `f3c33ed` `run_gold_condition.sh`, `compare_conditions.py` + 테스트 (전체 651 passed, 3 deselected)

## 확인
- 실데이터: `compare_conditions.py runs/gold-weather-l2 --baseline v1 v2` → 37과제 짝, d 0, 기준선 0.7027. `diagnostics/gold.jsonl` 77개 해시 변화 없음.
- 감싸기 `run_l3.sh` 가짜 저장소 시험: 거부된 실행은 이어 돌리지 않고 빠짐, 보통 멈춘 실행은 이어 돌림, 시작 실패 4번이면 멈춤.
- 검토(신선한 검토자 1명): Critical/Important 없음.

## Ruling (사용자 몫으로 내린 판단)
- Ruling: A단계 예측을 "네 조건 모두 차이 없음, `self`가 가장 불확실"로 적음(인계 문서의 예측은 B만 있었음).
- Ruling: 별도 계획 문서 없이 설계 → 테스트 먼저 → 구현으로 진행(사용자가 절차를 가볍게 하자는 데 동의).
- Ruling: 안전 거부가 있는 멈춘 실행은 감싸기 스크립트가 이어 돌리지 않고 바로 빼도록 함(메모리 규칙).
- Ruling: 정답 파일에 없는 과제(v1의 08·10·20)는 "짝 없음"으로 세지 않음.
- Ruling: 파일럿(첫 과제 × 네 조건)을 본 실행의 일부로 남김(설계 6절).

## minor (deferred)
- minor (deferred): `run_gold_condition.sh`가 OUT 안의 기존 실행 조건(judges/context)을 확인하지 않음 — 감싸기가 폴더-조건을 고정하고 `check_l3.py`가 사후 확인.
- minor (deferred): `compare_conditions` 출력에 중복 실행을 표시하지 않음 — `check_l3.py`가 중복을 보고.
- minor (deferred): 시작 실패한 이어 돌리기도 3회 한도에 셈 → 긴 서버 장애 시 과제가 빠질 수 있음(멈추는 쪽으로 실패).
- minor (deferred): `analyze_l3.py`가 짝 0개·grok 답 0개에서 오류.
- 참고(보고서에 한 문장): `all`의 다른 저자 심사 3개는 기준선과 요청·시드가 같지만 CLI 백엔드는 다시 뽑으므로 `all − 기준선`에 재추출 잡음이 섞임.

## 파일럿
- 2026-10-04 19:59–20:12, `weather-v1-01` × 네 조건. 시간: self 2.1분, shared_trace 3.5분, all 4.3분, author_label 2.2분 → 과제당 약 12분, 남은 36과제 약 7.2시간.
- `check_l3.py`: problems none. 0세대 쓰기 4개 모두 기록에서, 답 내용 같음. 심사 호출 self 4 / shared_trace 12 / all 16 / author_label 12 (모두 실시간).
- 프롬프트 직접 확인: shared_trace에 `Current population` + c001–c004 "not scored yet", author_label에 `Author of this answer: claude-opus-5-5`, self는 맥락 블록 없음.

## 본 실행
- 2026-10-04 20:12:15 시작: `setsid nohup bash run_l3.sh > main.log` (PID 1478658). 순서 self → shared_trace → all → author_label.
- 끝나면: `python check_l3.py runs/gold-weather-l3-{self,shared_trace,all,author_label}` → `python analyze_l3.py > analysis.md`.
- 2026-10-05 02:23:22 끝. 네 조건 모두 37/37, 이어 돌리기 0, 빠진 과제 0, 이상(anomaly) 0. `check_l3.py`: problems none (`check.txt`).

## 결과 (분석: `analysis.md`, 조건별 `runs/gold-weather-l3-<조건>/compare.json`)
판정: **네 조건 모두 "차이 없음"**. 예측과 같음 → B단계는 돌리지 않음(설계 1·4절).

| 조건 | 1위 정답 점수 (조건/기준선) | 평균 d | 나음/나쁨 | p (나쁨 쪽) | 판정 |
|---|---|---|---|---|---|
| self | 0.622 / 0.703 | −0.081 | 5 / 11 | 0.105 | 차이 없음 |
| shared_trace | 0.716 / 0.703 | +0.013 | 2 / 2 | 0.688 | 차이 없음 |
| all | 0.676 / 0.703 | −0.027 | 0 / 2 | 0.25 | 차이 없음 |
| author_label | 0.716 / 0.703 | +0.013 | 2 / 2 | 0.688 | 차이 없음 |

보조(판정 아님): 일치도 기준선 0.495, self 0.351, shared_trace 0.515, all 0.485, author_label 0.505.
self에서 1위 저자 glm 25/37(가장 관대한 심사위원의 자기 점수가 1위를 정함), all에서 gpt 26/37.
shared_trace와 author_label의 숫자가 같은 것은 우연: 점수 벡터 동일 0/37, 1위 저자 다른 과제 8개, 바뀐 과제도 서로 다름.

- Ruling: 조건 하나가 끝날 때마다 감싸기 스크립트가 일치도(보조 수치)를 로그에 찍어서, self의 일치도 0.35는 실행 중에 봄. 판정(기준선 비교)은 넷 다 끝난 뒤에 처음 열었음.
