# 기후 편차 세트 2단계 (진화) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 선택압이 정답을 보지 못할 때 세대를 거치면 정답이 나아지는지를, 37과제 × 3세대로 사전 등록한 규칙에 따라 판정하고 보고한다.

**Architecture:**
- 0세대는 새로 쓰지 않는다. 1단계에서 돌린 0세대 실행을 `--replay`로 재생해 같은 답·같은 점수에서 출발하고, 엔진이 1~3세대만 새로 만든다.
- 판정 규칙은 `diagnose/gold.py`의 `level2()`에 코드와 테스트로 넣고, 실행 전에 커밋한다. 보고서(`report.json`)와 분석 문서(`analysis.md`)가 판정을 출력한다.
- 새 스크립트 `scripts/run_gold_evolve.sh`가 과제를 하나씩 재생·진화시키고 마지막에 채점한다. 엔진과 프로토콜은 바꾸지 않는다.

**Tech Stack:** Python 3.11 이상(표준 라이브러리), bash, pytest. 엔진은 기존 `reasonlineage`.

**Spec:** `specs/2026-10-03-gold-weather-level2-design.md` (판정 규칙 5.1, 일관성 5.3, 실행 6, 오류 7)

**미리 확인한 것 (2026-10-03):**
- **0세대 재생은 모델을 부르지 않는다.** 37과제 모두를 `--generations 0`으로 재생하니 호출 592개가 모두 기록에서 왔고(`replayed: true`), 과제당 1초쯤 걸렸다. 그 실행들로 다시 계산한 1단계가 37과제 / 답 148 / 정답률 0.5270 / 쌍 97 / 일치도 0.4948 / 신호 없음으로 설계 5.3과 정확히 같았다.
- **`--replay`는 기록이 없는 호출을 멈추지 않고 새로 부른다**(`--gen0-from`만 멈춘다). 그래서 Task 5의 건식 재생과 Task 7의 확인이 0세대를 지킨다.
- 파일럿 `weather-v2-01`의 0세대 적합도는 c001 opus 0.632, c002 gpt 0.613, c003 grok 0.5645, c004 glm 0.59다. 첫 선택의 생존자는 **c001, c002**다(프로토콜 여유값 0.03).
- 9월 30일에 실제로 3세대를 돌린 두 실행에서 1–3세대에 과제당 24.5분, 25분이 걸렸다(세대 하나가 3.8–16.5분). 37과제면 약 15시간이다.
- Task 1–3을 `gold-weather-l2`의 새 복사본에 차례로 적용하며 단계마다 Run 명령을 돌렸다. RED는 아래 Expected처럼 실패했고 GREEN은 통과했다. 전체 테스트는 612 → 621 → 624 → 635 passed, 3 deselected다.
- Task 6의 감싸기 스크립트는 가짜 엔진으로 시험했다: 계속 멈추는 과제는 3번 이어 돌린 뒤 빠지고, 나머지는 끝까지 돌고, 마지막에 채점한다. Task 6·7의 확인 코드는 9월 30일 실행으로 돌려 봤다.

## Global Constraints

**작업 환경**
- 원래 체크아웃 `/common/jungj2/project/ReasonLineage`의 브랜치 `gold-weather-l2`(`gold-weather` 위)에서 한다. 추적되지 않은 `gb.html`은 커밋하지 않는다. 푸시하지 않는다.
- 테스트는 `python -m pytest -q`로 돌린다. 엔진 명령은 `PYTHONPATH=src python -m reasonlineage …`로 부른다.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`를 붙인다.
- 작업 폴더는 `.superpowers/sdd/2026-10-03-gold-weather-level2/`다(진행 기록, 감싸기 스크립트, 로그, 건식 재생).

**보안과 개인정보**
- API 키 파일(`~/.config/reasonlineage/*.env`)은 어떤 도구로도 열지 않는다.
- 사용자의 이메일이나 개인 식별 정보를 어떤 외부 요청에도 넣지 않는다.

**엔진을 얼려 둔다**
- `src/reasonlineage/engine`, `core`, `backends`, `protocol`은 이 계획 내내 바꾸지 않는다. 확인: `git diff --stat 015a81e -- src/reasonlineage/engine src/reasonlineage/core src/reasonlineage/backends src/reasonlineage/protocol`의 출력이 비어 있어야 한다.

**실행과 멈춤**
- 실행(모델 호출)은 이 계획의 승인으로 승인된 것으로 본다. 모델 호출은 Task 6에서만 한다.
- 멈춰 묻는 곳: 건식 재생이 어긋날 때(Task 5 Step 3), 파일럿 확인이 어긋날 때(Task 6 Step 3), 빠진 과제가 4개가 될 때(Task 6 Step 5), 일관성 확인이 어긋날 때(Task 7 Step 2).
- **다른 세트의 실행이 돌고 있으면 기다린다.** `ps -eo args | grep -E "run_set\.sh|run_l2\.sh|reasonlineage (run|resume)" | grep -v grep`로 확인한다(`pgrep -f`는 자기 셸 명령을 잡으므로 쓰지 않는다).
- 긴 실행은 `setsid nohup`으로 분리한다. 기다릴 때는 30분짜리 감시(Monitor)를 다시 걸며 기다린다.
- 제공자가 거부하면 과제를 버리기 전에 이미 정상으로 돌아간 과제로 대조 확인부터 한다. 안전 관련 거부면 그 과제를 빼고 다시 묻지 않는다.

**고정한 값 (설계 5.1, 결과를 본 뒤 바꾸지 않는다)**
- 과제 37개: `weather-v1`의 01–20에서 08, 10, 20을 뺀 17개와 `weather-v2`의 20개.
- 3세대, 실험 모드, `recuse` + `isolated`, 프로토콜 1.0.5, seed는 재생하는 실행의 것.
- 과제마다 `d = 최종 개체군 적합도 1위의 정답 점수 − 0세대 적합도 1위의 정답 점수`.
- 개선: 평균 d ≥ +0.10 그리고 단측 부호검정 p < 0.05. 악화: 평균 d ≤ −0.10 그리고 반대 방향 p < 0.05. 그 밖은 변화 없음.
- 예측: 개선이 아니다.

## Review Focus

명세가 바라지만 다른 테스트가 건드리지 않는 입력들이다. 각 줄의 확인은 그 일을 맡은 Task에 들어 있다.
- **재생이 기록 없는 0세대 호출을 조용히 새로 부르면 0세대가 바뀐다.** `--replay`는 멈추지 않는다(Task 5 Step 3의 건식 재생, Task 7 Step 2의 `generation-0 calls not from the record: 0`).
- **정답 파일의 과제가 재생되지 않고 조용히 빠지면 판정의 분모가 줄어든다.** 0세대가 끝나지 않은 과제는 스크립트가 멈추고(Task 3 `test_evolve_stops_when_a_gold_task_has_an_unfinished_generation_zero`), 과제 수는 일관성 확인이 센다(Task 7 Step 2).
- **평균 d가 정확히 ±0.10인 경계가 부동소수 오차로 흔들리면 판정이 바뀐다**(Task 1 `test_change_needs_both_the_size_and_the_sign_test`의 첫째·셋째 경우).
- **d = 0인 과제는 평균에는 들어가고 부호검정에서는 빠져야 한다**(Task 1 `test_tasks_without_change_dilute_the_mean_but_leave_the_sign_test`).
- **최종 1위 답이 정답 항목을 빠뜨리면 그 과제는 판정에서 빠지고 수가 보고돼야 한다**(Task 1 `test_level2_reports_the_change_in_the_best_answer_and_leaves_out_unscorable_tasks`, Task 2 `test_the_report_prints_the_level2_verdict`).

## File Structure

| 파일 | 하는 일 | Task |
|---|---|---|
| `src/reasonlineage/diagnose/gold.py` (수정) | 판정 상수, `change_verdict()`, `level2()`의 `change`, 보고서·분석 문서 출력 | 1, 2 |
| `tests/test_gold_diagnose.py` (수정) | 판정과 출력 테스트 | 1, 2 |
| `scripts/run_gold_evolve.sh` (새) | 0세대를 재생하며 세대를 이어 가고, 끝나면 채점 | 3 |
| `tests/test_gold_scripts.py` (수정) | 스크립트 테스트(가짜 `python`) | 3 |
| `gold/weather-l2/gold.json` (새) | 37과제의 정답, 뺀 과제와 이유 | 5 |
| `runs/gold-weather-l2/` | 2단계 실행, `report.json`, `analysis.md`, (있으면) `left_out.txt` | 6, 7 |

---

### Task 1: 사전 등록 판정

**Files:**
- Modify: `src/reasonlineage/diagnose/gold.py` (맨 위 규칙 상수, `level2()`의 끝)
- Modify: `tests/test_gold_diagnose.py` (import, 새 테스트)

**Interfaces:**
- Consumes: 기존 `level2(runs)`의 `per_task`(과제마다 `gen0_best`, `final_best`), `sign_test(concordant, discordant)`, `_mean(values)`(소수 넷째 자리 반올림, 빈 목록이면 `None`).
- Produces: 상수 `GAIN = 0.10`, `ALPHA = 0.05`. `change_verdict(diffs: Sequence[float]) -> dict` — 키는 `tasks`, `mean`, `up`, `down`, `p_up`, `p_down`, `verdict`(`"gain"`, `"loss"`, `"no change"`), `rules`(`{"gain", "alpha"}`). `level2(runs)["change"]` = `change_verdict(...)`에 `left_out`(정답 점수가 없어 빠진 과제 수)을 더한 것. Task 2와 Task 7이 쓴다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_diagnose.py`의 import를 바꾼다.

찾을 부분:
```python
from reasonlineage.diagnose.gold import (author_judge, borda, correctness, format_analysis, level1, level2,
                                         score_run, summarize)
```

바꿀 내용:
```python
from reasonlineage.diagnose.gold import (author_judge, borda, change_verdict, correctness, format_analysis,
                                         level1, level2, score_run, summarize)
```

`def test_runs_without_gold_unfinished_changed_or_not_runs_are_reported(tmp_path):` **바로 위에** 다음을 넣는다.

```python
@pytest.mark.parametrize("diffs, verdict", [
    ([0.5] * 10 + [0.0] * 40, "gain"),        # mean exactly +0.10, p = 0.001
    ([0.5] * 9 + [0.0] * 41, "no change"),    # p is small but the mean is 0.09
    ([-0.5] * 10 + [0.0] * 40, "loss"),       # mean exactly -0.10
    ([0.5] * 5, "gain"),                      # 5 up, 0 down: p = 0.031
    ([0.5] * 4, "no change"),                 # 4 up, 0 down: p = 0.0625, a large mean is not enough
    ([1.0, 1.0, 0.0, -0.5], "no change"),     # mean 0.375 but 2 up, 1 down: p = 0.5
])
def test_change_needs_both_the_size_and_the_sign_test(diffs, verdict):
    assert change_verdict(diffs)["verdict"] == verdict


def test_tasks_without_change_dilute_the_mean_but_leave_the_sign_test():
    assert change_verdict([0.5] * 5 + [0.0] * 20) | {"rules": None} == {
        "tasks": 25, "mean": 0.1, "up": 5, "down": 0, "p_up": 0.03125, "p_down": 1.0, "verdict": "gain", "rules": None}
    assert change_verdict([0.5] * 5 + [0.0] * 21)["verdict"] == "no change"  # mean 0.0962


def test_no_tasks_means_no_change():
    assert change_verdict([]) | {"rules": None} == {
        "tasks": 0, "mean": None, "up": 0, "down": 0, "p_up": None, "p_down": None, "verdict": "no change", "rules": None}


def test_level2_reports_the_change_in_the_best_answer_and_leaves_out_unscorable_tasks(tmp_path):
    worse = [answer("c005", 1, "opus", ["C", "A", "B"], 0.9)]       # the final best is half right; generation 0's was right
    run1 = write_run(tmp_path, "run1", "t1", aligned() + worse, final=["c005", "c001", "c002", "c003"])
    blank = [answer("c005", 1, "opus", ["B", "C"], 0.9)]            # leaves out A: the final best has no correctness
    run2 = write_run(tmp_path, "run2", "t2", aligned() + blank, final=["c005", "c001", "c002", "c003"])
    report = level2([score_run(run1, GOLD), score_run(run2, GOLD)])
    assert report["change"] == {"tasks": 1, "mean": -0.5, "up": 0, "down": 1, "p_up": 1.0, "p_down": 0.5,
                                "verdict": "no change", "rules": {"gain": 0.1, "alpha": 0.05}, "left_out": 1}
```

- [ ] **Step 2: 돌려서 실패를 보기**

Run: `python -m pytest tests/test_gold_diagnose.py -q`
Expected: `1 error`, `ImportError: cannot import name 'change_verdict' from 'reasonlineage.diagnose.gold'`

- [ ] **Step 3: 판정 쓰기**

`src/reasonlineage/diagnose/gold.py` 맨 위의 규칙 상수를 바꾼다.

찾을 부분:
```python
# Level-1 rules, fixed before any run (gold design 6.2). Do not change them after seeing results.
CEILING = 0.8
MIN_PAIRS = 10
SIGNAL = 0.7
_EPS = 1e-9
```

바꿀 내용:
```python
# Level-1 rules, fixed before any run (gold design 6.2). Do not change them after seeing results.
CEILING = 0.8
MIN_PAIRS = 10
SIGNAL = 0.7
# Level-2 rule, fixed before the level-2 run (weather level-2 design 5.1). Do not change it after seeing results.
GAIN = 0.10
ALPHA = 0.05
_EPS = 1e-9
```

`level2()`의 끝을 바꾼다. `change_verdict()`는 `level2()` 바로 뒤에 새로 생긴다.

찾을 부분:
```python
    means = {key: _mean([t[key] for t in per_task if t[key] is not None]) for key in ("gen0_best", "final_best", "gen0_vote")}
    return {"tasks": len(evolved), "per_task": per_task, "mean": means,
            "by_generation": {str(g): {"fitness": _mean(v["fitness"]), "correctness": _mean(v["correctness"]),
                                       "answers": len(v["fitness"])} for g, v in sorted(generations.items())}}
```

바꿀 내용:
```python
    means = {key: _mean([t[key] for t in per_task if t[key] is not None]) for key in ("gen0_best", "final_best", "gen0_vote")}
    diffs = [t["final_best"] - t["gen0_best"] for t in per_task if t["final_best"] is not None and t["gen0_best"] is not None]
    return {"tasks": len(evolved), "per_task": per_task, "mean": means,
            "by_generation": {str(g): {"fitness": _mean(v["fitness"]), "correctness": _mean(v["correctness"]),
                                       "answers": len(v["fitness"])} for g, v in sorted(generations.items())},
            "change": change_verdict(diffs) | {"left_out": len(per_task) - len(diffs)}}


def change_verdict(diffs: Sequence[float]) -> dict[str, Any]:
    """Did evolution change the best answer's correctness? d = final best minus generation-0 best, one per task.

    Gain or loss needs both a mean change of at least GAIN and a one-sided sign test below ALPHA (weather level-2
    design 5.1); tasks where d is 0 leave the sign test.
    """
    up = sum(d > _EPS for d in diffs)
    down = sum(d < -_EPS for d in diffs)
    mean = _mean(list(diffs))
    p_up, p_down = sign_test(up, down), sign_test(down, up)
    if mean is not None and mean >= GAIN - _EPS and p_up is not None and p_up < ALPHA:
        verdict = "gain"
    elif mean is not None and mean <= -GAIN + _EPS and p_down is not None and p_down < ALPHA:
        verdict = "loss"
    else:
        verdict = "no change"
    return {"tasks": len(diffs), "mean": mean, "up": up, "down": down, "p_up": p_up, "p_down": p_down,
            "verdict": verdict, "rules": {"gain": GAIN, "alpha": ALPHA}}
```

- [ ] **Step 4: 돌려서 통과를 보기**

Run: `python -m pytest tests/test_gold_diagnose.py -q`
Expected: `28 passed`

Run: `python -m pytest -q`
Expected: `621 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add src/reasonlineage/diagnose/gold.py tests/test_gold_diagnose.py
git commit -m "Add the pre-registered level-2 verdict

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: 판정을 보고서와 분석 문서에 출력

**Files:**
- Modify: `src/reasonlineage/diagnose/gold.py` (`format_report()`의 끝, `format_analysis()`의 Tasks 절 앞)
- Modify: `tests/test_gold_diagnose.py` (import, 새 테스트)

**Interfaces:**
- Consumes: Task 1의 `level2(runs)["change"]`.
- Produces: `format_report()`의 2단계 마지막 줄 `  change in the best answer (final - generation 0): … -> <verdict>`. `format_analysis()`의 `## Level 2 (evolution)` 절(진화한 실행이 있을 때만). 도우미 `_p()`, `_change_summary()`. Task 7이 `analysis.md`를 읽는다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_diagnose.py`의 import에 `format_report`를 더한다. Task 1이 만든 import를 다음으로 바꾼다.

```python
from reasonlineage.diagnose.gold import (author_judge, borda, change_verdict, correctness, format_analysis,
                                         format_report, level1, level2, score_run, summarize)
```

`def test_runs_without_gold_unfinished_changed_or_not_runs_are_reported(tmp_path):` **바로 위에**(Task 1의 테스트 뒤에) 다음을 넣는다.

```python
def _evolved(tmp_path):
    worse = [answer("c005", 1, "opus", ["C", "A", "B"], 0.9)]
    blank = [answer("c005", 1, "opus", ["B", "C"], 0.9)]
    return [score_run(write_run(tmp_path, "run1", "t1", aligned() + worse, final=["c005", "c001", "c002", "c003"]), GOLD),
            score_run(write_run(tmp_path, "run2", "t2", aligned() + blank, final=["c005", "c001", "c002", "c003"]), GOLD)]


def test_the_report_prints_the_level2_verdict(tmp_path):
    text = format_report(summarize(_evolved(tmp_path)))
    assert text.splitlines()[-1] == (
        "  change in the best answer (final - generation 0): mean -0.500 over 1 task(s), 0 up / 1 down, "
        "sign test p = 1 (up) / 0.5 (down); 1 task(s) left out because an answer left out a gold item -> no change")


def test_the_analysis_gives_the_level2_verdict_the_rule_and_each_generation(tmp_path):
    text = format_analysis(_evolved(tmp_path))
    assert "## Level 2 (evolution)" in text and "**Verdict: no change.** Change in the best answer" in text
    assert "a mean change of at least 0.10 and a one-sided sign test p below 0.05" in text
    assert "Mean correctness: generation-0 best 1.0, final best 0.5, generation-0 vote 0.5." in text
    assert "| 1 | 1 | 0.9 | 0.5 |" in text  # generation 1: the unscorable answer is not counted
    assert text.index("## Level 2") < text.index("## Tasks")


def test_the_analysis_has_no_level2_section_without_evolution(tmp_path):
    assert "## Level 2" not in format_analysis(scored(tmp_path, [aligned()]))
```

- [ ] **Step 2: 돌려서 실패를 보기**

Run: `python -m pytest tests/test_gold_diagnose.py -q`
Expected: `2 failed, 29 passed`. 보고서 줄과 분석 절 테스트가 실패한다.
- `test_the_analysis_has_no_level2_section_without_evolution`은 지금도 통과한다. 새 절이 진화한 실행에만 나오도록 지키는 회귀 테스트라서 그렇다.

- [ ] **Step 3: 출력 쓰기**

`format_report()`의 끝을 바꾼다. `_p()`와 `_change_summary()`가 그 뒤에 새로 생긴다.

찾을 부분:
```python
        lines.append("  by generation: " + ", ".join(f"{g}: fitness {v['fitness']} correctness {v['correctness']}"
                                                  for g, v in two["by_generation"].items()))
    return "\n".join(lines)
```

바꿀 내용:
```python
        lines.append("  by generation: " + ", ".join(f"{g}: fitness {v['fitness']} correctness {v['correctness']}"
                                                  for g, v in two["by_generation"].items()))
        lines.append(f"  change in the best answer (final - generation 0): {_change_summary(two['change'])} "
                     f"-> {two['change']['verdict']}")
    return "\n".join(lines)


def _p(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3g}"


def _change_summary(change: Mapping[str, Any]) -> str:
    mean = "n/a" if change["mean"] is None else f"{change['mean']:+.3f}"
    left = f"; {change['left_out']} task(s) left out because an answer left out a gold item" if change["left_out"] else ""
    return (f"mean {mean} over {change['tasks']} task(s), {change['up']} up / {change['down']} down, "
            f"sign test p = {_p(change['p_up'])} (up) / {_p(change['p_down'])} (down){left}")
```

`format_analysis()`의 Tasks 절 앞에 2단계 절을 넣는다.

찾을 부분:
```python
    lines += ["", "## Tasks", "", "Each cell: the author's top pick, its correctness (✓ 1, ½ 0.5, ✗ 0) and the "
              "answer's fitness.", ""]
```

바꿀 내용:
```python
    two = level2(runs)
    if two:
        change, mean = two["change"], two["mean"]
        rules = change["rules"]
        lines += ["", "## Level 2 (evolution)", "",
                  f"**Verdict: {change['verdict']}.** Change in the best answer (final - generation 0): "
                  f"{_change_summary(change)}.",
                  f"Rule fixed before the run: gain or loss needs a mean change of at least {rules['gain']:.2f} and a "
                  f"one-sided sign test p below {rules['alpha']:.2f}.",
                  f"Mean correctness: generation-0 best {mean['gen0_best']}, final best {mean['final_best']}, "
                  f"generation-0 vote {mean['gen0_vote']}.", "",
                  "| Generation | Answers | Mean fitness | Mean correctness |", "|---|---|---|---|"]
        lines += [f"| {g} | {v['answers']} | {v['fitness']} | {v['correctness']} |" for g, v in two["by_generation"].items()]
    lines += ["", "## Tasks", "", "Each cell: the author's top pick, its correctness (✓ 1, ½ 0.5, ✗ 0) and the "
              "answer's fitness.", ""]
```

- [ ] **Step 4: 돌려서 통과를 보기**

Run: `python -m pytest tests/test_gold_diagnose.py -q`
Expected: `31 passed`

Run: `python -m pytest -q`
Expected: `624 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add src/reasonlineage/diagnose/gold.py tests/test_gold_diagnose.py
git commit -m "Print the level-2 verdict in the report and the analysis

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: 0세대를 재생하며 진화시키는 스크립트

**Files:**
- Create: `scripts/run_gold_evolve.sh`
- Modify: `tests/test_gold_scripts.py` (첫머리, 끝에 테스트 추가)

**Interfaces:**
- Consumes: `reasonlineage run TASK --replay RUN_DIR --generations N --out OUT`, `reasonlineage gold --gold GOLD RUNS… --out … --analysis …`. 0세대 실행 폴더의 이름은 `<날짜>-<시각>-<과제 id>`다.
- Produces: `scripts/run_gold_evolve.sh OUT GOLD GENERATIONS SET [SET ...]`. `OUT/left_out.txt`(한 줄에 과제 id 하나)에 있는 과제는 건너뛴다. Task 6이 쓴다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`tests/test_gold_scripts.py`의 첫머리를 바꾼다.

찾을 부분:
```python
"""The gold-set scripts: building repoDB task files from a curation record, and the level-1 run script."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
```

바꿀 내용:
```python
"""The gold-set scripts: building repoDB task files from a curation record, the level-1 run script, and the
level-2 script that replays generation 0 and evolves further."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
```

파일 끝에 다음을 붙인다.

```python
# --- the level-2 script (weather level-2 design 6.2) ---

def test_evolve_script_is_valid_bash():
    assert subprocess.run(["bash", "-n", str(ROOT / "scripts" / "run_gold_evolve.sh")]).returncode == 0


def evolve_copy(tmp_path, gold_ids=("wx-01", "wx-03")):
    """A checkout with one set of three finished generation-0 runs, a gold file naming two of them, and a fake
    `python` that only logs its calls."""
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "run_gold_evolve.sh", root / "scripts")
    (root / "tasks" / "wx").mkdir(parents=True)
    for task_id in ("wx-01", "wx-02", "wx-03"):
        (root / "tasks" / "wx" / f"{task_id}.json").write_text("{}")
        run = root / "runs" / "gold-wx" / f"20261003-120000-{task_id}"
        run.mkdir(parents=True)
        (run / "header.json").write_text("{}")
        (run / "result.json").write_text("{}")
    gold = tmp_path / "gold.json"
    gold.write_text(json.dumps({"source": {"left_out": ["wx-02"]}, "tasks": {i: {} for i in gold_ids}}, indent=2))
    bin_dir, log = tmp_path / "bin", tmp_path / "python.log"
    bin_dir.mkdir()
    (bin_dir / "python").write_text(f'#!/usr/bin/env bash\necho "$PYTHONPATH|$*" >> "{log}"\n')
    (bin_dir / "python").chmod(0o755)
    return root, gold, log, {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}


def run_evolve(root, env, *args):
    return subprocess.run(["bash", str(root / "scripts" / "run_gold_evolve.sh"), *map(str, args)],
                          capture_output=True, text=True, env=env)


def test_evolve_replays_each_gold_task_with_more_generations_then_scores(tmp_path):
    root, gold, log, env = evolve_copy(tmp_path)
    out = tmp_path / "out"
    result = run_evolve(root, env, out, gold, 3, "wx")
    assert result.returncode == 0, result.stderr
    calls = [line.split("|") for line in log.read_text().splitlines()]
    assert {path for path, _ in calls} == {str(root / "src")}
    runs = [args for _, args in calls if args.startswith("-m reasonlineage run ")]
    assert runs == [f"-m reasonlineage run {root}/tasks/wx/{i}.json --replay {root}/runs/gold-wx/20261003-120000-{i} "
                    f"--generations 3 --out {out}" for i in ("wx-01", "wx-03")]  # wx-02 is not in the gold file
    assert calls[-1][1].startswith(f"-m reasonlineage gold --gold {gold} ")
    assert calls[-1][1].endswith(f"--out {out}/report.json --analysis {out}/analysis.md")


def test_evolve_skips_a_task_already_finished(tmp_path):
    root, gold, log, env = evolve_copy(tmp_path)
    done = tmp_path / "out" / "20261004-010000-wx-01"
    done.mkdir(parents=True)
    (done / "header.json").write_text("{}")
    (done / "result.json").write_text("{}")
    result = run_evolve(root, env, tmp_path / "out", gold, 3, "wx")
    assert result.returncode == 0, result.stderr
    assert "skip wx-01: already finished" in result.stdout
    runs = [line for line in log.read_text().splitlines() if "reasonlineage run " in line]
    assert len(runs) == 1 and "wx-03.json" in runs[0]


def test_evolve_skips_a_task_left_out_after_repeated_stops(tmp_path):
    root, gold, log, env = evolve_copy(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "left_out.txt").write_text("wx-01\n")
    result = run_evolve(root, env, out, gold, 3, "wx")
    assert result.returncode == 0, result.stderr
    assert "skip wx-01: left out after repeated stops" in result.stdout
    runs = [line for line in log.read_text().splitlines() if "reasonlineage run " in line]
    assert len(runs) == 1 and "wx-03.json" in runs[0]


def test_evolve_stops_at_a_run_that_did_not_finish(tmp_path):
    root, gold, log, env = evolve_copy(tmp_path)
    stopped = tmp_path / "out" / "20261004-010000-wx-01"
    stopped.mkdir(parents=True)
    (stopped / "header.json").write_text("{}")
    result = run_evolve(root, env, tmp_path / "out", gold, 3, "wx")
    assert result.returncode == 1 and "resume" in result.stderr and "wx-01" in result.stderr
    assert not log.exists()


def test_evolve_stops_when_a_gold_task_has_an_unfinished_generation_zero(tmp_path):
    root, gold, log, env = evolve_copy(tmp_path)
    (root / "runs" / "gold-wx" / "20261003-120000-wx-03" / "result.json").unlink()
    result = run_evolve(root, env, tmp_path / "out", gold, 3, "wx")
    assert result.returncode == 1 and "generation-0 run of wx-03" in result.stderr
    assert "reasonlineage gold" not in (log.read_text() if log.exists() else "")


def test_evolve_stops_on_a_set_without_runs(tmp_path):
    root, gold, log, env = evolve_copy(tmp_path)
    result = run_evolve(root, env, tmp_path / "out", gold, 3, "wx", "nope")
    assert result.returncode == 1 and "no generation-0 runs in runs/gold-nope" in result.stderr
    assert "reasonlineage gold" not in log.read_text()


@pytest.mark.parametrize("args, message", [
    (("OUT", "GOLD", "3"), "usage: scripts/run_gold_evolve.sh OUT GOLD GENERATIONS SET"),
    (("OUT", "GOLD", "0", "wx"), "GENERATIONS must be a whole number of at least 1"),
    (("OUT", "GOLD", "three", "wx"), "GENERATIONS must be a whole number of at least 1"),
])
def test_evolve_refuses_wrong_arguments(tmp_path, args, message):
    root, gold, log, env = evolve_copy(tmp_path)
    result = run_evolve(root, env, *args)
    assert result.returncode == 2 and message in result.stderr
    assert not log.exists()


def test_evolve_stops_without_a_gold_file(tmp_path):
    root, gold, log, env = evolve_copy(tmp_path)
    result = run_evolve(root, env, tmp_path / "out", tmp_path / "missing.json", 3, "wx")
    assert result.returncode == 1 and "no gold file" in result.stderr
    assert not log.exists()
```

- [ ] **Step 2: 돌려서 실패를 보기**

Run: `python -m pytest tests/test_gold_scripts.py -q`
Expected: `11 failed, 7 passed`, `FileNotFoundError: … scripts/run_gold_evolve.sh`(아직 없는 스크립트를 복사하려다 실패)

- [ ] **Step 3: 스크립트 쓰기**

`scripts/run_gold_evolve.sh`를 만들고 실행 권한을 준다.

```bash
#!/usr/bin/env bash
# Level-2 measurement (weather level-2 design 6.2): each finished generation-0 run of the listed sets whose task
# is in GOLD is replayed with GENERATIONS generations of evolution, one task at a time; then the gold summary
# (report.json) and the analysis (analysis.md). Generation 0 comes from the record and is not written again.
# A task that already has a finished run in OUT is skipped, and so is a task listed in OUT/left_out.txt (one id per
# line; a task that kept stopping is left out and reported, design 7). A task whose run stopped halfway stops the
# script: resume that run first, then run the script again.
#
#   scripts/run_gold_evolve.sh OUT GOLD GENERATIONS SET [SET ...]
#   e.g. scripts/run_gold_evolve.sh runs/gold-weather-l2 gold/weather-l2/gold.json 3 weather-v1 weather-v2
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USAGE="usage: scripts/run_gold_evolve.sh OUT GOLD GENERATIONS SET [SET ...]"
if [ "$#" -lt 4 ]; then
  echo "$USAGE" >&2
  exit 2
fi
OUT="$1"; GOLD="$2"; GENERATIONS="$3"; shift 3
export PYTHONPATH="$ROOT/src"   # this checkout's code, not an installed copy
if ! [[ "$GENERATIONS" =~ ^[1-9][0-9]*$ ]]; then
  echo "GENERATIONS must be a whole number of at least 1, not '$GENERATIONS'" >&2
  exit 2
fi
if [ ! -f "$GOLD" ]; then
  echo "no gold file $GOLD" >&2
  exit 1
fi
mkdir -p "$OUT"
for SET in "$@"; do
  if ! compgen -G "$ROOT/runs/gold-$SET/*/header.json" > /dev/null; then
    echo "no generation-0 runs in runs/gold-$SET" >&2
    exit 1
  fi
  for source in "$ROOT"/runs/gold-"$SET"/*/; do
    source="${source%/}"
    name="$(basename "$source")"
    id="${name#*-*-}"   # run folders are named <date>-<time>-<task id>
    if ! grep -qF "\"$id\":" "$GOLD"; then
      continue          # not part of this measurement
    fi
    if [ -f "$OUT/left_out.txt" ] && grep -qxF "$id" "$OUT/left_out.txt"; then
      echo "skip $id: left out after repeated stops (see $OUT/left_out.txt)"
      continue
    fi
    if [ ! -f "$source/result.json" ]; then
      echo "stop: the generation-0 run of $id in runs/gold-$SET did not finish; it cannot be replayed" >&2
      exit 1
    fi
    task="$ROOT/tasks/$SET/$id.json"
    if [ ! -f "$task" ]; then
      echo "stop: $id has a generation-0 run but no task file tasks/$SET/$id.json" >&2
      exit 1
    fi
    if compgen -G "$OUT/*-$id/result.json" > /dev/null; then
      echo "skip $id: already finished"
      continue
    fi
    if compgen -G "$OUT/*-$id/header.json" > /dev/null; then
      echo "stop: $id has a run in $OUT that did not finish; resume it with" \
           "'PYTHONPATH=$ROOT/src python -m reasonlineage resume <run folder>', then run this script again" >&2
      exit 1
    fi
    python -m reasonlineage run "$task" --replay "$source" --generations "$GENERATIONS" --out "$OUT"
  done
done
python -m reasonlineage gold --gold "$GOLD" "$OUT"/*/ --out "$OUT/report.json" --analysis "$OUT/analysis.md"
```

- [ ] **Step 4: 돌려서 통과를 보기**

Run: `chmod +x scripts/run_gold_evolve.sh && python -m pytest tests/test_gold_scripts.py -q`
Expected: `18 passed`

Run: `python -m pytest -q`
Expected: `635 passed, 3 deselected`

- [ ] **Step 5: 커밋**

```bash
git add scripts/run_gold_evolve.sh tests/test_gold_scripts.py
git commit -m "Add the script that replays generation 0 and evolves further

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: 실행 전 검토

Task 5–7은 데이터 파일과 실행만 더하고 코드는 더하지 않는다. 그래서 executing-plans의 **브랜치 최종 검토를 여기서, 15시간 실행 전에** 한다. 실행 뒤에 찾은 결함은 비싸다.

**Files:** 없음 (검토 결과와 수정은 진행 기록과 커밋에 남는다)

- [ ] **Step 1: 검토 꾸러미 만들기**

```bash
SP=/home/jungj2/.claude/plugins/cache/claude-plugins-official/superpowers/6.4.1/skills
bash $SP/subagent-driven-development/scripts/review-package plans/2026-10-03-gold-weather-level2.md 015a81e HEAD
```

Expected: `wrote …/review-015a81e..<HEAD>.diff: N commit(s)`

- [ ] **Step 2: 신선한 검토자에게 맡기기**

`superpowers:requesting-code-review`의 `code-reviewer.md` 절차로, 가장 능력 있는 모델을 **명시해서** 검토자 하나를 보낸다. 넘길 것: 꾸러미 경로, 이 계획과 설계 문서 경로, 위 Review Focus 절 그대로, 진행 기록의 `Ruling:` 줄. 검토자는 파일을 고치지 않고, 네트워크와 모델을 부르지 않고, `~/.config/reasonlineage/`를 열지 않는다.

- [ ] **Step 3: 등급을 다시 매기고 고치기**

- Critical과 Important는 한 번의 수정 단계에서 고친다. 고칠 때마다 결함을 재현하는 테스트를 먼저 쓰고 실패를 본 뒤 고치고, 전체 테스트를 돌린다. 진행 기록에 `Final: fixed <결함> — <테스트> RED→GREEN, suite N/N`으로 적는다.
- 고치지 않기로 한 것은 `Final: Ruling:`으로, Minor는 `Final: minor (deferred):`로 적는다.
- 엔진·코어·백엔드·프로토콜을 고쳐야 하는 결함이 나오면 실행을 시작하지 않고 사용자에게 알린다(엔진을 얼려 둔다는 제약 때문이다).

Expected: 수정이 있으면 커밋되고 `python -m pytest -q`가 모두 통과한다.

---

### Task 5: 정답 파일과 건식 재생

**Files:**
- Create: `gold/weather-l2/gold.json`
- Create (커밋하지 않음): `.superpowers/sdd/2026-10-03-gold-weather-level2/check_l2.py`, `…/dry/`

**Interfaces:**
- Consumes: `gold/weather-v1/gold.json`, `gold/weather-v2/gold.json`, `runs/gold-weather-v{1,2}/`
- Produces: 37과제의 정답 파일. 확인 스크립트 `check_l2.py OUT GOLD`(Task 7도 쓴다).

- [ ] **Step 1: 정답 파일 만들기**

```bash
python - <<'PY'
import json
from pathlib import Path
left_out = ["weather-v1-08", "weather-v1-10", "weather-v1-20"]
tasks, sources = {}, {}
for name in ("weather-v1", "weather-v2"):
    gold = json.load(open(f"gold/{name}/gold.json"))
    sources[name] = gold["source"]
    tasks.update({k: v for k, v in gold["tasks"].items() if k not in left_out})
assert len(tasks) == 37, len(tasks)
body = {"source": {"from": sources, "left_out": left_out,
                   "why": "the question's premise was false: no candidate was above its 1901-2000 normal",
                   "design": "specs/2026-10-03-gold-weather-level2-design.md 4.1"},
        "tasks": dict(sorted(tasks.items()))}
out = Path("gold/weather-l2/gold.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(len(body["tasks"]), "tasks in", out)
PY
```

Expected: `37 tasks in gold/weather-l2/gold.json`

- [ ] **Step 2: 엔진이 그대로인지 확인**

```bash
git diff --stat 015a81e -- src/reasonlineage/engine src/reasonlineage/core src/reasonlineage/backends src/reasonlineage/protocol
```

Expected: 출력 없음

- [ ] **Step 3: 37과제의 0세대만 재생하고 확인하기 (모델 호출 없음)**

확인 스크립트를 작업 폴더에 둔다.

```bash
W=.superpowers/sdd/2026-10-03-gold-weather-level2
mkdir -p $W
cat > $W/check_l2.py <<'PY'
import json, re, statistics as st, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, "src")
from reasonlineage.diagnose.gold import level1, score_run

OUT, GOLD = Path(sys.argv[1]), json.load(open(sys.argv[2]))
HEDGE = re.compile(r"\b(uncertain|uncertainty|cannot know|can't know|no data|don't have|do not have|forecast|"
                   r"likely|probably|may|might|could|plausibl\w*|guess|estimate\w*|confidence|low confidence)\b", re.I)
runs, live, selections, created, texts = [], 0, {}, {}, {}
for d in sorted(OUT.glob("*/")):
    if not (d / "result.json").is_file():
        continue
    r = score_run(d, GOLD)
    if r["status"] != "scored":
        continue
    runs.append(r)
    for line in open(d / "events.jsonl"):
        e = json.loads(line)
        if e["event"] == "call.completed" and e["name"].startswith("g0/") and e.get("replayed") is not True:
            live += 1
        elif e["event"] == "selection":
            selections.setdefault(r["run"], {})[e["generation"]] = set(e["survivors"])
        elif e["event"] == "candidate.created":
            created[(r["run"], e["id"])] = e
            texts[(r["run"], e["id"])] = e["answer"]["answer"]

print(f"A. generation-0 calls not from the record: {live}")
one = level1(runs)
rate = "n/a" if one["concordance"] is None else f"{one['concordance']:.4f}"
print(f"B. level 1 from these runs: tasks {one['tasks']} answers {one['answers']} share {one['share_correct']:.4f} "
      f"pairs {one['pairs']} concordance {rate} -> {one['verdict']}")

print("C. survivors' authors at each selection")
for g in sorted({g for s in selections.values() for g in s}):
    authors = Counter(created[(t, i)]["author"] for t, s in selections.items() for i in s.get(g, ()))
    print(f"   selection after generation {g}: {dict(authors)}")

kept = sum(any(a["correctness"] == 1 for a in r["answers"] if a["id"] in set(r["final"])) for r in runs)
print(f"D. tasks whose final population still holds a fully correct answer: {kept} of {len(runs)}")

print("E. crossover offspring by synthesizer")
for author in ("opus", "gpt", "grok", "glm"):
    mine = [a for r in runs for a in r["answers"] if a["operator"] == "crossover" and a["author"] == author]
    def survived(r, a):
        nxt = selections.get(r["run"], {}).get(a["generation"])
        return None if nxt is None else a["id"] in nxt
    flags = [s for r in runs for a in r["answers"] if a["operator"] == "crossover" and a["author"] == author
             for s in [survived(r, a)] if s is not None]
    scored = [a["correctness"] for a in mine if a["correctness"] is not None]
    print(f"   {author:>5}: {len(mine):>3} written, survived the next selection {sum(flags)}/{len(flags)}, "
          f"mean correctness {st.mean(scored) if scored else float('nan'):.3f}")

print("F. hedging words per 1,000 characters, by generation")
for g in sorted({a["generation"] for r in runs for a in r["answers"]}):
    rates = [1000 * len(HEDGE.findall(texts[(r["run"], a["id"])])) / max(1, len(texts[(r["run"], a["id"])]))
             for r in runs for a in r["answers"] if a["generation"] == g]
    print(f"   generation {g}: {st.mean(rates):.2f} over {len(rates)} answers")
PY
```

건식 재생을 돌린다.

```bash
W=.superpowers/sdd/2026-10-03-gold-weather-level2
rm -rf $W/dry && mkdir -p $W/dry
for SET in weather-v1 weather-v2; do
  for src in runs/gold-$SET/*/; do
    src=${src%/}; id=$(basename $src); id=${id#*-*-}
    grep -qF "\"$id\":" gold/weather-l2/gold.json || continue
    PYTHONPATH=src python -m reasonlineage run tasks/$SET/$id.json --replay $src --generations 0 --out $W/dry > /dev/null || echo "FAILED $id"
  done
done
ls $W/dry | wc -l
PYTHONPATH=src python $W/check_l2.py $W/dry gold/weather-l2/gold.json | head -2
```

Expected:
```
37
A. generation-0 calls not from the record: 0
B. level 1 from these runs: tasks 37 answers 148 share 0.5270 pairs 97 concordance 0.4948 -> no signal
```
- `FAILED` 줄이 있거나 세 값 중 하나라도 다르면 **멈추고** 사용자에게 알린다. 본 실행을 시작하지 않는다.
- 건식 재생은 1분 안에 끝난다. 오래 걸리면 기록 없는 호출이 실제로 모델을 부르고 있는 것이니 멈춘다.

- [ ] **Step 4: 커밋**

```bash
git add gold/weather-l2/gold.json
git commit -m "Add the gold file of the 37 level-2 tasks

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: 파일럿과 본 실행

**Files:**
- Create: `runs/gold-weather-l2/*/` (git이 추적하지 않음)
- Create (커밋하지 않음): `.superpowers/sdd/2026-10-03-gold-weather-level2/run_l2.sh`, `pilot_check.py`, `pilot.log`, `main.log`

**Interfaces:**
- Consumes: Task 3의 스크립트, Task 5의 정답 파일
- Produces: 37개(또는 빠진 과제를 뺀 수) 실행과 `runs/gold-weather-l2/report.json`, `analysis.md`. Task 7이 읽는다.

- [ ] **Step 1: 다른 실행이 없는지 확인**

```bash
ps -eo args | grep -E "run_set\.sh|run_l2\.sh|reasonlineage (run|resume)" | grep -v grep || echo "no engine run"
```

Expected: `no engine run`. 다른 실행이 있으면 끝날 때까지 기다린다.

- [ ] **Step 2: 파일럿 한 과제 돌리기**

```bash
W=.superpowers/sdd/2026-10-03-gold-weather-level2
(PYTHONPATH=src setsid nohup python -m reasonlineage run tasks/weather-v2/weather-v2-01.json \
   --replay runs/gold-weather-v2/20261003-124808-weather-v2-01 --generations 3 --out runs/gold-weather-l2 \
   > $W/pilot.log 2>&1 < /dev/null &)
```

`result.json`이 생길 때까지 기다린다(약 25분). 감시 예: `until compgen -G "runs/gold-weather-l2/*-weather-v2-01/result.json" >/dev/null || ! ps -eo args | grep -q "[r]easonlineage run"; do sleep 60; done`
- 실행이 `result.json` 없이 멈추면 5분 뒤 `PYTHONPATH=src python -m reasonlineage resume <그 실행 폴더>`로 이어 돌린다. 최대 3번이고, 그래도 안 끝나면 **멈추고** 사용자에게 알린다(파일럿은 기계 확인용이라 빼고 넘어가지 않는다).

- [ ] **Step 3: 파일럿을 확인하기 (정답 점수는 보지 않는다)**

```bash
W=.superpowers/sdd/2026-10-03-gold-weather-level2
cat > $W/pilot_check.py <<'PY'
import json, sys
from datetime import datetime
from pathlib import Path
(run,) = Path(sys.argv[1]).glob(f"*-{sys.argv[2]}/")
ev = [json.loads(line) for line in open(run / "events.jsonl")]
g0 = [e for e in ev if e["event"] == "call.completed" and e["name"].startswith("g0/")]
print("generation-0 calls:", len(g0), "| from the record:", sum(e.get("replayed") is True for e in g0))
first = next(e for e in ev if e["event"] == "selection" and e["generation"] == 0)
print("first selection survivors:", first["survivors"])
generation = {e["id"]: e["generation"] for e in ev if e["event"] == "candidate.created"}
done = {}
for e in ev:
    if e["event"] == "candidate.scored":
        done[generation[e["candidate"]]] = datetime.fromisoformat(e["ts"])
print("minutes per generation:", {g: round((done[g] - done[g - 1]).total_seconds() / 60, 1) for g in sorted(done) if g >= 1})
print("finished:", (run / "result.json").is_file())
PY
python $W/pilot_check.py runs/gold-weather-l2 weather-v2-01
```

Expected:
```
generation-0 calls: 16 | from the record: 16
first selection survivors: ['c001', 'c002']
minutes per generation: {1: …, 2: …, 3: …}
finished: True
```
- 앞의 두 줄 중 하나라도 다르면 **멈추고** 사용자에게 알린다.
- 세대별 시간으로 전체 시간 추정을 고쳐 진행 기록에 적는다(36과제 × 세 값의 합).
- 이 확인 코드는 정답 점수를 출력하지 않는다. 파일럿의 정답은 37과제가 끝날 때까지 보지 않는다(설계 6.1).

- [ ] **Step 4: 본 실행을 분리해서 돌리기**

감싸기 스크립트를 작업 폴더에 두고 돌린다. 파일럿은 이미 끝났으므로 스크립트가 건너뛴다.

```bash
W=.superpowers/sdd/2026-10-03-gold-weather-level2
cat > $W/run_l2.sh <<'SH'
#!/usr/bin/env bash
# Run the level-2 measurement to the end (level-2 design 6.2, 7). A run that stopped (header, no result) is resumed
# after 5 minutes. A task whose run stops a fourth time is left out: its folder moves to runs/gold-weather-l2-left-out/
# and its id goes into runs/gold-weather-l2/left_out.txt, which run_gold_evolve.sh skips. Four left-out tasks stop
# everything, and so does a failure with no stopped run to resume.
set -u
cd "${REPO:-/common/jungj2/project/ReasonLineage}"
export PYTHONPATH=src
OUT=runs/gold-weather-l2
declare -A resumes
while true; do
  stopped=0
  for d in "$OUT"/*/; do
    d="${d%/}"
    if [ ! -f "$d/header.json" ] || [ -f "$d/result.json" ]; then continue; fi
    stopped=1
    name="$(basename "$d")"; id="${name#*-*-}"
    resumes[$id]=$(( ${resumes[$id]:-0} + 1 ))
    if [ "${resumes[$id]}" -gt 3 ]; then
      mkdir -p "$OUT-left-out" && mv "$d" "$OUT-left-out/" && echo "$id" >> "$OUT/left_out.txt"
      echo "== $(date '+%F %T') left out $id after 3 resumes"
      if [ "$(wc -l < "$OUT/left_out.txt")" -ge 4 ]; then
        echo "== $(date '+%F %T') stopped: 4 tasks left out; decide with the user (design 7)"; exit 1
      fi
      continue
    fi
    echo "== $(date '+%F %T') resume $d (${resumes[$id]} of 3, after a pause)"
    sleep "${RESUME_WAIT:-300}"
    python -m reasonlineage resume "$d" || echo "== $(date '+%F %T') resume of $d stopped again"
  done
  if scripts/run_gold_evolve.sh "$OUT" gold/weather-l2/gold.json 3 weather-v1 weather-v2; then break; fi
  if [ "$stopped" -eq 0 ] && ! compgen -G "$OUT/*/header.json" > /dev/null; then
    echo "== $(date '+%F %T') stopped: the script failed with no stopped run to resume"; exit 1
  fi
  echo "== $(date '+%F %T') a run stopped"
done
echo "== $(date '+%F %T') done"
SH
chmod +x $W/run_l2.sh
(setsid nohup bash $W/run_l2.sh > $W/main.log 2>&1 < /dev/null &)
```

기다리는 동안 30분짜리 감시를 다시 건다. 감시 조건: `report.json`이 생기거나, `run_l2.sh`가 더 이상 돌지 않거나. 사용자가 물으면 끝난 과제 수(`ls runs/gold-weather-l2/*/result.json | wc -l`)와 남은 시간을 알린다.

- [ ] **Step 5: 끝난 뒤 수를 세기**

```bash
tail -5 .superpowers/sdd/2026-10-03-gold-weather-level2/main.log
echo "finished: $(ls runs/gold-weather-l2/*/result.json | wc -l)"
cat runs/gold-weather-l2/left_out.txt 2>/dev/null || echo "left out: none"
```

Expected: `== … done`, `finished: 37`, `left out: none`
- 빠진 과제가 있으면 수와 id를 진행 기록에 적는다. 1–3개면 Task 7로 간다(판정은 남은 과제로 하고, 빠진 수를 보고한다).
- `main.log`가 `stopped: 4 tasks left out` 또는 `stopped: the script failed with no stopped run to resume`으로 끝났으면 **멈추고** 사용자에게 알린다.

---

### Task 7: 판정과 보고

**Files:**
- Read: `runs/gold-weather-l2/report.json`, `analysis.md`
- Modify (저장소 밖): 메모리 `gold-weather-result.md`, `MEMORY.md`

**Interfaces:**
- Consumes: Task 6의 실행, Task 5의 `check_l2.py`
- Produces: 사용자에게 보내는 결론, 메모리 기록

- [ ] **Step 1: 엔진이 그대로였는지 확인**

```bash
git diff --stat 015a81e -- src/reasonlineage/engine src/reasonlineage/core src/reasonlineage/backends src/reasonlineage/protocol
```

Expected: 출력 없음

- [ ] **Step 2: 일관성 확인 (판정보다 먼저)**

```bash
W=.superpowers/sdd/2026-10-03-gold-weather-level2
PYTHONPATH=src python $W/check_l2.py runs/gold-weather-l2 gold/weather-l2/gold.json | tee $W/check.txt
```

Expected (앞의 두 줄):
```
A. generation-0 calls not from the record: 0
B. level 1 from these runs: tasks 37 answers 148 share 0.5270 pairs 97 concordance 0.4948 -> no signal
```
- 빠진 과제가 있으면 B의 과제 수와 수치는 그만큼 다르다. 그때는 같은 과제로 건식 재생 폴더(`$W/dry`)의 해당 실행만 빼고 다시 계산한 값과 비교한다.
- A가 0이 아니면, 0세대가 기록에서 오지 않은 과제를 찾아 판정에서 빼고 보고한다(설계 7). 그런 과제가 4개 이상이면 **멈추고** 사용자에게 알린다.
- 그 밖에 B가 다르면 **멈추고** 사용자에게 알린다. 판정을 계산하지 않는다.

- [ ] **Step 3: 판정 읽기**

```bash
python -c "
import json; two = json.load(open('runs/gold-weather-l2/report.json'))['level2']
c = two['change']; print('verdict:', c['verdict'], '| tasks', c['tasks'], '| left out', c['left_out'],
  '| mean d', c['mean'], '| up', c['up'], 'down', c['down'], '| p_up', c['p_up'], 'p_down', c['p_down'])
print('mean correctness:', two['mean'])
print('by generation:', two['by_generation'])"
sed -n '/## Level 2/,/## Tasks/p' runs/gold-weather-l2/analysis.md
```

Expected: 판정 한 줄(`gain`, `loss`, `no change` 중 하나), 평균 정답 점수(0세대 1위 0.703, 0세대 다수결 0.676이 기준선), 세대별 표.

- [ ] **Step 4: 보조 수치**

Step 2의 `check.txt` 셋째 줄부터가 보조 수치다(설계 5.2).
- C: 선택마다 생존자의 저자. 첫 선택은 opus·gpt 36·37, glm 1, grok 0이어야 한다(1단계 계산과 같아야 한다).
- D: 최종 개체군에 완전히 맞은 답이 남은 과제 수
- E: 교배 자손을 합성한 저자별 수, 다음 선택 생존율, 정답 점수(grok·glm이 합성한 자손에 주목한다)
- F: 세대별 얼버무림 비율

- [ ] **Step 5: 사용자에게 알리고 기록하기**

- 한 줄 결론으로 시작한다: 개선 / 악화 / 변화 없음, 그리고 미리 적은 예측("개선 아님")과 맞는지.
- 근거 수치를 두세 줄로: 평균 d, 오른 과제·내린 과제, 부호검정 p, 0세대 1위·최종 1위·다수결 비교.
- 보조 수치에서 눈에 띄는 것을 두세 줄로: grok·glm이 합성한 자손이 살아남았는지, 세대가 갈수록 얼버무림이 늘었는지, 정답이 개체군에서 사라졌는지.
- 1단계와 나란히 적는다. 보고서 경로를 링크한다.
- 메모리 `gold-weather-result.md`에 2단계 결과를 더하고, `MEMORY.md`의 한 줄을 고친다.
- 진행 기록의 `Ruling:`과 `minor (deferred)` 줄을 모아 최종 메시지에 적는다.
