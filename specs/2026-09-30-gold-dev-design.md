# 정답지 개발용 세트 (repoDB) 설계

- 날짜: 2026-09-30
- 상태: 설계 1/4 · 2/4 · 3/4 · 4/4 승인, 문서 검토 대기
- 기반: `specs/2026-09-29-engine-design.md` (엔진 1단계, 프로토콜 1.0.1, 패널 opus · gpt · grok · glm)
- 브랜치: `worktree-gold-standard-v0`

## 1. 목적과 범위

파일럿에서 세대가 갈수록 적합도는 올랐지만, 답이 스스로 매긴 유망도는 내려갔어요. 이것이 더 정확해진 것인지 심사자 취향에 맞춘 것인지는 외부 정답이 있어야 알 수 있어요. 정답으로 확인하는 순서는 세 단계예요.

1. 1세대 심사 점수(적합도)가 정답을 따라가는가
2. 진화가 정답률을 올리는가
3. 심사 조건에 따라 "점수는 오르는데 정답률은 제자리"인 간극이 달라지는가 (심사 편향 논문)

1단계가 안 되면 2·3단계는 해석할 수 없어서, 1단계부터 해요. 데이터는 repoDB로 만든 개발용 세트예요. 모델이 결과를 알고 있을 가능성이 커서 논문 결과로는 쓰지 않고, 도구와 절차를 맞춰 보는 리허설로만 써요. 논문용은 모든 모델의 학습 컷오프 이후에 결과가 나온 정답지 v0로 따로 만들어요.

**이 문서의 범위**
- repoDB에서 후보 뽑기, ClinicalTrials.gov 임상 기록 받기, 검수 기록, 과제·정답 파일 만들기
- 엔진 변경: `--generations 0`, `--replay`와 `--generations` 함께 쓰기, `--replay`의 과제 확인, `python -m reasonlineage`
- `reasonlineage gold` 명령: 모든 세대의 모든 답을 정답으로 채점하고, 1단계 판정과 2단계 비교를 계산
- 과제 10개로 1단계 실측

**범위 밖**
- 2단계 실측 (1단계 결과를 보고 정해요)과 2단계 판정 기준 (2단계를 돌리기 전에 정해요)
- 정답지 v0 (컷오프 이후 결과) 구축
- 조건 비교 실험 (3단계)
- repoDB 원본 파일을 저장소에 넣는 것

## 2. 성공 기준

1. 과제 파일, 정답 파일, 검수 기록이 저장소에 있고, 같은 입력(고정한 repoDB 파일, 저장한 임상 기록, 검수 기록)에서 같은 파일이 다시 만들어져요.
2. 엔진은 정답 파일을 읽지 않아요. `engine/`과 `checks/`는 `gold`와 `diagnose.gold`를 import하지 않아요 (테스트로 확인).
3. `--generations 0` 실행은 1세대 작성과 심사가 끝나면 멈춰요. `--replay … --generations 3`은 기록된 1세대를 모델 호출 없이 재사용해요 (테스트로 확인).
4. `reasonlineage gold`가 6.2의 규칙대로 1단계 판정을 내요 (테스트로 확인).
5. 과제 10개로 1단계 실측을 끝내고, 판정 결과를 보고해요.

## 3. 구조 (설계 1/4)

**원칙:** 엔진은 정답을 보지 않아요. 정답은 별도 파일에 두고, 실행이 끝난 뒤 분석 도구만 읽어요. J2의 정답 항목 파일(`--gold-items`)과 같은 방식이에요.

| 새 파일 | 하는 일 |
|---|---|
| `src/reasonlineage/gold/__init__.py` | 정답지 도구 패키지 |
| `src/reasonlineage/gold/repodb.py` | repoDB 파일을 받아 체크섬을 확인하고, 후보 적응증을 뽑아요 |
| `src/reasonlineage/gold/trials.py` | ClinicalTrials.gov에서 임상 기록을 받아 저장해요 |
| `src/reasonlineage/gold/build.py` | 검수 기록으로 과제 파일과 정답 파일을 만들어요 |
| `src/reasonlineage/diagnose/gold.py` | 답을 정답으로 채점하고, 1단계 판정과 2단계 비교를 계산해요 |
| `src/reasonlineage/__main__.py` | `python -m reasonlineage` |
| `scripts/build_repodb_dev.py` | 후보 뽑기 → 임상 기록 → (검수) → 파일 만들기를 순서대로 실행해요 |
| `scripts/run_gold_dev.sh` | 과제 10개를 순서대로 돌리고 `reasonlineage gold`로 요약해요 |
| `gold/repodb-dev/candidates.json` | 후보 적응증과 실패 쌍 (자동) |
| `gold/repodb-dev/trials.json` | 실패 쌍의 임상 기록 (자동) |
| `gold/repodb-dev/curation.json` | 검수 결정과 이유 (Claude가 쓰고 사용자가 확인) |
| `gold/repodb-dev/gold.json` | 과제별 정답과 출처 (자동) |
| `tasks/repodb-dev/*.json` | 과제 10개 (엔진 과제 형식, 엔진 설계 5.1) |

**흐름**

```
repoDB 파일 (고정한 사본) ─ repodb.py ─> candidates.json ─ trials.py ─> trials.json
                                                                          │
                                                   검수 (Claude) ─> curation.json
                                                                          │
                                        build.py ─> tasks/repodb-dev/*.json + gold/repodb-dev/gold.json
tasks ─ reasonlineage run --generations 0 ─> runs/gold-dev/<실행>/
runs/gold-dev/* + gold.json ─ reasonlineage gold ─> <실행>/diagnostics/gold.jsonl + report.json
```

## 4. 과제 만들기 (설계 2/4)

### 4.1 출처 고정
- 파일: `zietzm/repoDB` 저장소, 커밋 `c921b2610f596a40cee2a538de37f9f29d3dfd06` (2019-02-04)의 `data/repoDB.csv`
- 주소: `https://raw.githubusercontent.com/zietzm/repoDB/c921b2610f596a40cee2a538de37f9f29d3dfd06/data/repoDB.csv`
- sha256: `c5424d26b190ea207f6d343620eea748f845b0f28cad811eaf3a158797e0ef23` (1,073,050 bytes)
- 원 데이터: Brown & Patel, *Scientific Data* 2017 (`adam-sam-brown/repoDB`, figshare 모음 3462048). 원래 웹앱 주소(apps.chiragjpgroup.org)는 2026-09-30에 접속되지 않았어요.
- 받은 파일은 저장소 밖 캐시(기본 `~/.cache/reasonlineage/repodb/`)에 둬요. 체크섬이 다르면 멈춰요.

### 4.2 후보 뽑기 (`repodb.py`)
- 열: `drug_name`, `drug_id`, `ind_name`, `ind_id`, `NCT`, `status`, `phase`, `DetailedStatus`
- 적응증은 `ind_id`(UMLS)로 묶어요.
- 승인된 약: `status`가 `Approved`
- 실패한 약: 다음을 모두 만족해요.
  - `status`가 `Terminated`, `Withdrawn`, `Suspended` 중 하나
  - `DetailedStatus`가 효능 또는 안전성 패턴에 맞음 (대소문자 무시)
    - 효능: `efficac|futil|no (significant )?(benefit|effect|difference)|not effective|ineffective|lack of (clinical )?(benefit|response|activity)|did not (meet|show|demonstrate)|primary (end ?point|outcome)|interim analysis|unlikely to (meet|succeed|show)|insufficient (activity|response|benefit)`
    - 안전성: `safety|adverse|toxicit|side effect|serious`
  - 그 적응증에 승인된 약이 아님
- 승인된 약이 1개 이상이고 실패한 약이 2개 이상인 적응증만 남겨요. 2026-09-30 기준 21개예요.
- 결과: `candidates.json`. 적응증마다 승인된 약 목록과 실패 쌍 목록(약, NCT, 상태, 단계, 중단 사유)이 들어가요.

### 4.3 임상 기록 받기 (`trials.py`)
- 주소: `https://clinicaltrials.gov/api/v2/studies/{NCT}?fields=NCTId,BriefTitle,OverallStatus,WhyStopped,InterventionName,Phase,Condition`
- 실패 쌍의 NCT마다 제목, 상태, 중단 사유, 투여 약, 단계, 질환을 `trials.json`에 저장해요. 이미 저장된 NCT는 다시 받지 않아요.
- 실패하면 한 번 다시 받고, 그래도 실패하면 그 NCT에 오류를 적어 두고 검수에서 판단해요.

### 4.4 검수 (`curation.json`)
- 실패한 약으로 인정하는 조건 (모두 만족)
  1. 그 약이 그 임상의 시험 약이에요. 병용 요법의 배경 약이 아니에요.
  2. 그 질환 자체를 치료하려는 임상이에요. 다른 증상이나 합병증(예: 암 환자의 우울증)을 위한 임상이 아니에요.
  3. 효능 부족(무익, 1차 평가변수 미달 포함)이나 안전성 때문에 멈췄어요.
- 승인된 약은 그 적응증에 승인된 약(repoDB `Approved`) 가운데 하나를 골라요. 대안이 있으면 가장 널리 쓰이는 1차 치료제는 피해요 (천장 효과를 줄이려고).
- 과제 하나는 승인된 약 1개와 실패한 약 2개로, 모두 다른 약이에요. 적응증 하나에서 과제는 하나만 만들어요.
- 형식:

```json
{
  "tasks": [
    {"id": "repodb-rheumatoid-arthritis", "ind_id": "C0003873", "indication": "Rheumatoid Arthritis",
     "display_name": "rheumatoid arthritis",
     "approved": {"drug": "…", "why": "…"},
     "failed": [{"drug": "…", "ncts": ["NCT…"], "why": "…"}, {"drug": "…", "ncts": ["NCT…"], "why": "…"}]}
  ],
  "dropped": [{"ind_id": "…", "indication": "…", "why": "…"}]
}
```

- 검수는 Claude가 하고, 사용자는 이 파일로 결정과 이유를 확인해요. 과제가 10개가 안 되면 몇 개인지 보고하고, 기준 완화 여부를 사용자와 정해요.

### 4.5 과제·정답 파일 (`build.py`)
- 과제 파일: `tasks/repodb-dev/<id>.json`, 엔진 과제 형식(엔진 설계 5.1)이에요.
  - `id`: `repodb-` + `display_name`을 소문자·하이픈으로 바꾼 것
  - `question`: `Which of these drugs is most promising for treating {display_name}? Rank the candidates, and give the mechanism, the key evidence, and a validation experiment for the top pick.`
    - 파일럿 질문에 있던 "repurpose"는 쓰지 않아요. 이미 승인된 약을 1위에 둔 답을 심사자가 "재창출이 아니다"라며 감점할 수 있어서예요.
  - `candidates`: 세 약을 `random.Random(int(sha256(id)[:8], 16))`로 섞은 순서예요. 승인된 약이 늘 같은 자리에 오지 않고, 같은 id면 늘 같은 순서예요.
  - `category`: `biomedical`, `data_sensitivity`: `public`
- 정답 파일: `gold/repodb-dev/gold.json`

```json
{
  "source": {"repo": "zietzm/repoDB", "commit": "c921b2610f596a40cee2a538de37f9f29d3dfd06",
             "path": "data/repoDB.csv", "sha256": "c5424d26b190ea207f6d343620eea748f845b0f28cad811eaf3a158797e0ef23"},
  "tasks": {"repodb-rheumatoid-arthritis": {"approved": ["…"], "failed": ["…", "…"]}}
}
```

## 5. 엔진 변경과 실행 방법 (설계 3/4)

### 5.1 1세대만 돌리기: `--generations 0`
- `core/state.py`: 세대 수 범위를 1–10에서 0–10으로 넓혀요.
- `engine/header.py`: 실험 모드 사전 점검의 "세대 수 1 이상"을 "0 이상"으로 바꿔요.
- 러너는 바꾸지 않아요. 선택 단계가 이미 세대 한도를 확인하므로, 0이면 1세대 작성과 심사 뒤 `run.completed`(`termination: generation_limit`, `generation: 0`)로 끝나요.
- 호출 수: 작성 4 + 심사 12 (다시 맞추기가 있으면 그만큼 더)

### 5.2 진화 이어 가기: `--replay <실행> --generations N`
- `cli.py`: `--replay`일 때 세대 수는 `--generations`가 주어지면 그 값, 아니면 원래 실행의 값이에요. 모드, 심사 조건, 맥락, seed는 원래 실행의 값을 그대로 써요.
- 헤더의 `options.generations`에는 실제로 쓴 값이, `replay_from`에는 원래 실행이 기록돼요.
- 기록된 1세대 작성·심사와 J1 점검은 모두 재사용하고(호출 0), 세대 1–N만 새로 불러요.
- **안전장치:** `--replay`도 원래 실행의 과제(헤더의 `task`)가 주어진 과제와 다르면 시작 전에 멈춰요. 과제가 다르면 아무것도 재사용되지 않고 전부 새로 부르게 되기 때문이에요. 프로토콜 해시는 비교하지 않아요. 바뀐 호출만 새로 부르는 것이 `--replay`의 설계예요 (엔진 설계 6.5).

### 5.3 `python -m reasonlineage`
- `src/reasonlineage/__main__.py`가 `cli.main`을 불러요. 설치된 `reasonlineage` 명령은 설치한 폴더의 코드를 가리키므로, 워크트리 코드로 돌릴 때 써요.

### 5.4 `reasonlineage gold`

```
reasonlineage gold --gold GOLD.json RUN_DIR [RUN_DIR ...] [--out REPORT.json]
```

- 실행 폴더마다
  - 헤더의 과제 id로 정답을 찾아요. 정답 파일에 없으면 경고하고 건너뛰어요.
  - `result.json`이 없으면 "미완료"로 표시하고 계산에서 빼요.
  - `events.jsonl`의 `candidate.created`(답), `candidate.scored`(적합도), `judge.scored`(심사자별 점수)로 모든 답을 채점해서 `diagnostics/gold.jsonl`에 써요. 한 줄에 답 하나이고, 답 id, 세대, 연산, 작성 모델, 적합도, 심사자별 가중 점수, 정답 점수가 들어가요.
- 전체 요약: 1단계 판정(6.2)과 2단계 비교(6.3, 세대가 1 이상인 실행만)를 화면에 보여 주고, `--out`이 있으면 JSON으로 저장해요.

## 6. 채점과 판정 (설계 4/4)

### 6.1 정답 점수
- (승인된 약, 실패한 약) 쌍 가운데 답의 순위에서 승인된 약이 더 위에 있는 비율이에요.
- 과제가 승인 1 + 실패 2이므로, 승인된 약이 1위면 1, 2위면 0.5, 3위면 0이에요.
- 엔진이 답이 후보를 모두 순위에 넣도록 강제하므로 모든 답을 채점할 수 있어요.

### 6.2 1단계 판정 (실행 전에 고정)
- 대상: 각 과제의 1세대 답 4개
- 비교 쌍: 과제마다 6쌍, 모두 60쌍. 정답 점수가 다른 쌍만 세요.
- 일치: 적합도가 높은 쪽이 정답 점수도 높으면 1, 반대면 0, 적합도가 같으면 0.5
- 일치율 = 일치 합 / 정답 점수가 다른 쌍의 수
- 판정은 이 순서로 내려요.
  1. **보류 (천장):** 1세대 답 가운데 80% 이상(10개 과제면 40개 중 32개 이상)이 1점
  2. **보류 (쌍 부족):** 정답 점수가 다른 쌍이 10개 미만
  3. **신호 있음:** 일치율 0.70 이상
  4. **신호 없음:** 그 밖의 경우
- 함께 보고하지만 판정에는 쓰지 않는 것
  - 심사자별 일치율: 그 심사자가 두 답을 모두 채점한 쌍에서, 적합도 대신 그 심사자의 가중 점수로 계산
  - 모델별 정답률: 모델마다 1세대 답의 평균 정답 점수
  - 부호 검정 p값: 적합도가 같은 쌍을 뺀 일치·불일치 수로 계산한 단측 이항 검정
- 이 숫자들(80%, 10쌍, 0.70, 동점 0.5)은 결과를 본 뒤에 바꾸지 않아요.

### 6.3 2단계 비교 (계산만)
- 과제마다 다음 답들의 정답 점수를 계산해요.
  - 1세대에서 적합도가 가장 높은 답
  - 최종 세대 개체군에서 적합도가 가장 높은 답
  - 모델별 1세대 답
  - 1세대 다수결: 1세대 순위 4개를 Borda 방식(1위 2점, 2위 1점, 3위 0점)으로 합한 순위. 동점이면 과제 파일의 후보 순서를 따라요.
- 세대별 평균 적합도와 평균 정답 점수
- 2단계 판정 기준은 1단계 결과를 본 뒤, 2단계를 돌리기 전에 정해요.

### 6.4 오류 처리
- 정답 파일에 없는 과제의 실행: 경고하고 건너뛰어요.
- 끝나지 않은 실행: "미완료"로 표시하고 계산에서 빼요. 개수는 요약에 보고해요.
- repoDB 체크섬이 다름: 파일 만들기 단계에서 멈춰요.
- ClinicalTrials.gov 호출 실패: 한 번 다시 받고, 그래도 실패하면 오류를 기록해 둬요 (4.3).

## 7. 실측 계획
- `scripts/run_gold_dev.sh`
  - 과제 10개를 순서대로 `python -m reasonlineage run TASK --generations 0 --seed 1 --out runs/gold-dev`로 돌려요.
  - 끝나면 `python -m reasonlineage gold --gold gold/repodb-dev/gold.json runs/gold-dev/* --out runs/gold-dev/report.json`
- 패널과 조건: `configs/main.json`(opus, gpt, grok, glm), 실험 모드, 작성자 제외, 격리, 프로토콜 1.0.1, 웹 검색 없음
- 과제는 동시에 돌리지 않아요. Ollama Pro의 동시 요청 한도가 3개인데, 엔진은 모델마다 2개씩 부르기 때문이에요.
- 예상: 과제당 6–7분, 전체 약 70분. 모델 호출 약 160회, jev 점검 40회
- 실행이 멈추면 `resume`으로 이어 가요.
- 1단계 결과에 따라 다음을 정해요.
  - 신호 있음: 같은 10개로 2단계 (`--replay <실행> --generations 3`, 과제당 호출 약 24회, 약 25분)
  - 신호 없음: 심사나 과제 설계를 다시 봐요.
  - 보류: 과제를 더 어렵게 다시 만들어요.

## 8. 테스트
- **정답 점수:** 후보 순서가 섞여도 1 / 0.5 / 0이 맞게 나와요.
- **1단계 판정:** 가짜 실행 폴더로 일치율, 적합도 동점 0.5, 천장 판정, 쌍 부족 판정을 확인해요.
- **참고 지표와 2단계:** 심사자별 일치율, Borda 다수결(동점 처리 포함), 모델별 정답률, 세대별 평균을 확인해요.
- **`reasonlineage gold`:** 정답 파일에 없는 과제, 미완료 실행, `gold.jsonl`과 `--out` 파일을 확인해요.
- **repoDB 추출:** 작은 가짜 CSV로 상태·사유 필터, 승인된 약 제외, 2개 이상 조건, 체크섬 불일치 멈춤을 확인해요.
- **임상 기록:** 가짜 서버로 응답 해석, 이미 저장된 NCT 건너뛰기, 실패 기록을 확인해요.
- **파일 만들기:** 같은 id면 같은 순서로 섞이는지, 질문 문장, 정답 파일 형식을 확인해요.
- **엔진:**
  - `--generations 0`이면 가짜 패널 호출 16회 뒤 `run.completed`
  - `--replay … --generations 3`이면 1세대 호출 0회에 세대 1–3만 호출
  - `--replay`에 다른 과제를 주면 시작 전에 멈춤
- **격리:** `engine/`과 `checks/`가 `gold`와 `diagnose.gold`를 import하지 않아요 (기존 AST 검사 방식).
- 실제 호출 테스트는 늘리지 않아요. 7장의 실측이 그 역할이에요.

## 9. 지금 코드에서 바뀌는 것

| 파일 | 바뀌는 것 |
|---|---|
| `src/reasonlineage/core/state.py` | 세대 수 범위 0–10 |
| `src/reasonlineage/engine/header.py` | 실험 모드 세대 수 조건 0 이상 |
| `src/reasonlineage/cli.py` | `--replay`의 세대 수 덮어쓰기와 과제 확인, `gold` 명령 |
| `tests/test_state.py`, `tests/test_header.py`, `tests/test_cli.py`, `tests/test_isolation.py` | 위 변경의 테스트 |
| 새 파일 | 3장 표 |

## 10. 이 문서 밖에서 정할 것
- 2단계 판정 기준: 1단계 결과를 본 뒤, 2단계를 돌리기 전에 정해요.
- 정답지 v0: 모든 패널 모델의 학습 컷오프 이후 결과로 만든 논문용 시험 세트. 출처는 CT Open 2026 기간, openFDA 효능 추가 승인, Open Targets 변경분이에요 (엔진 설계 11장).
- 검수 뒤 과제가 10개가 안 될 때의 기준 완화
