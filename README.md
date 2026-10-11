# ReasonLineage

> **An evolutionary reasoning engine with author-recused, context-isolated LLM judging.**

ReasonLineage improves responses through repeated generation, critique, selection, mutation, and crossover. It preserves the ancestry of each response and separates structural checks from the LLM reviews used to calculate fitness. The same process can be applied to answers, analyses, designs, and scientific hypotheses.

---

## Table of Contents

1. [Overview — what ReasonLineage does](#1-overview--what-reasonlineage-does)
2. [Evolution — non-author review and selection](#2-evolution--non-author-review-and-selection)
3. [jev — check, optionally revise, recheck](#3-jev--check-optionally-revise-recheck)
4. [Architecture](#4-architecture)
5. [Quick Start](#5-quick-start)
6. [Usage in Detail](#6-usage-in-detail)
   - [6.1 Start a run](#61-start-a-run)
   - [6.2 Resume a run](#62-resume-a-run)
   - [6.3 Diagnose a finished run](#63-diagnose-a-finished-run)
   - [6.4 Score runs against a gold file](#64-score-runs-against-a-gold-file)
   - [6.5 Scripts](#65-scripts)
7. [ALS / AML pilot results](#7-als--aml-pilot-results)
8. [Environment variables and credentials](#8-environment-variables-and-credentials)
9. [Testing](#9-testing)
10. [License](#10-license)

---

## 1. Overview — what ReasonLineage does

| Capability | What it does |
|---|---|
| **Response evolution** | A panel of models writes responses. Survivors are kept, and new responses come from mutation and crossover. Every response keeps its parent links. |
| **Non-author fitness** | Models other than the author review each response. Reviews are aggregated by the median for each criterion and combined using the task's weights. |
| **jev structural checks** | Noul, Score, and Choice assessments check each new response before peer scoring. A confirmed gap can trigger one revision by the original author. jev values do not enter fitness. |
| **Recorded runs** | Model calls, events, and checks are written to a run folder, so a stopped run can be resumed and a finished run replayed, diagnosed, or scored against a gold file. |

Entry points:

- **CLI**: `reasonlineage run | resume | diagnose | gold` (also `python -m reasonlineage`)
- **Scripts**: study runners, gold-set builders, and calibration tools in [`scripts/`](scripts)
- **Workflow**: the [detailed workflow](SKILL.md), written as an agent skill

![ReasonLineage overview: model-diverse response evolution with non-author reviewers and compact jev checks](reports/figures/reasonlineage-jev-simple-types/overview.png)

The figure illustrates a four-model configuration: **Opus 5.5 (Anthropic), GPT-6.1 sol (OpenAI), Grok 4.7 (xAI), and GLM-5.3-flash (Z.ai)**. Model availability and the active reviewer panel are set by the execution profile. All displayed fitness values are illustrative.

---

## 2. Evolution — non-author review and selection

### 2.1 The problem: models judging their own work

The engine was built to test one question. When a model scores its own answers, or judges share the scoring record, does fitness keep rising across generations while correctness stays flat? And does removing the author from scoring, and judging each response in isolation, prevent it? To compare those conditions fairly, the code fixes who writes, who judges, and what is checked, so every condition runs the same procedure ([engine design](specs/2026-09-29-engine-design.md), Korean).

### 2.2 How ReasonLineage handles it

1. Each active model writes one initial response in the multi-model pilot. Other active models review that response; its author is excluded.
2. Reviews are aggregated by the median for each criterion and combined using the task's weights to obtain fitness.
3. Two responses survive selection. Retained responses reuse their scores.
4. The next generation adds one mutation by the parent response's author and one crossover by a model that authored neither parent.
5. New responses are checked and reviewed before the next selection. The best evaluated response is returned with its lineage.

Survivors are **responses**; selecting two does not permanently reduce the available model roster to two. In the single-model pilot, two isolated self-review calls replace the non-author panel, and two mutations replace mutation plus crossover.

### 2.3 Key design decision: code decides, models write and judge

| The engine (code) decides | The models do |
|---|---|
| who judges each response, and what the judge sees | write responses: initial, mutation, crossover |
| fitness: the per-criterion median, then the weighted sum | review and critique |
| selection and the generation count | choose which parts of each parent a crossover drops |
| records, protocol version, and mode checks | |

Two run options vary the judging, for experiments on judging bias. The defaults are `recuse` and `isolated`.

| `--judges` | Who scores a response |
|---|---|
| `recuse` | every panel model except the author (a one-model panel judges its own responses, each in a fresh session) |
| `self` | the author only |
| `same_family` | other panel models from the author's company |
| `other_vendor` | panel models from other companies |
| `all` | every panel model, the author included |

| `--context` | What the judge sees besides the question and the response |
|---|---|
| `isolated` | nothing else |
| `author_label` | the name of the author model |
| `shared_trace` | the current population, with scores from earlier selections |

---

## 3. jev — check, optionally revise, recheck

### 3.1 The problem: fitness does not check structure

Peer fitness and structural completeness measure different things. A response can be complete in form and still cite papers that do not support it. An interesting idea can lack the validation strategy that would make it a comparable research proposal. The J1 gate targets the second kind of gap: it decides when to send a response back and what to fix ([purpose and methods](reports/2026-10-09-reasonlineage-purpose-and-method.md), Korean).

### 3.2 How the gate works

The combined jev gate uses three parallel typed assessments:

| Type | Short label | Role |
|---|---|---|
| Noul | Present? | Check whether the required response or proposal is present. |
| Score | Adequate? | Check whether required components are sufficiently developed. |
| Choice | Priority gap? | Identify the component that most needs attention. |

Confirmed gaps can trigger **one revision by the original author**, followed by reinspection. Responses without confirmed gaps proceed directly to peer scoring. Unclear judgments can be rechecked once, and unresolved issues are recorded.

In the combined profile, Score's adequacy threshold is applied to **P(level 2) + P(level 3) < 0.5**. Choice selects the highest-probability priority gap, and a targeted revision requires agreement with the insufficient component scores. See the [combined-gate report](reports/2026-10-09-jev-combined.md) (Korean) for the complete decision rules and calibration.

### 3.3 Key design decision: jev checks, reviewers score

The structural gate does not directly add jev values to fitness; fitness remains the responsibility of the LLM reviewers. J2 diagnostics are recorded separately and do not drive survival or revision. In the code, checker results go to the run's `checks.jsonl`, never to the engine's event log, and J1's revision decision is the only way a check affects the run.

The rules above belong to the combined profile, [`research/co-scientist-pilot/protocol-jev-combined`](research/co-scientist-pilot/protocol-jev-combined), which sets `j1.enforce` to `true`. The packaged protocol that `reasonlineage run` loads, [`src/reasonlineage/protocol/protocol.json`](src/reasonlineage/protocol/protocol.json), has its own question set and sets `j1.enforce` to `false`: the gate records what it would revise without requesting the revision.

### 3.4 Evolution in motion

![Animated ReasonLineage lineage, non-author fitness review, and Noul/Score/Choice structural checks](reports/figures/reasonlineage-jev-simple-types/animation.gif)

[Interactive animation](reports/figures/reasonlineage-jev-simple-types/animation.html) · [MP4](reports/figures/reasonlineage-jev-simple-types/animation.mp4) · [SVG](reports/figures/reasonlineage-jev-simple-types/overview.svg) · [High-resolution PNG](reports/figures/reasonlineage-jev-simple-types/overview-native.png) · [Figure caption and production notes](reports/figures/reasonlineage-jev-simple-types/README.md)

Download the HTML animation and open it locally to use its playback controls; GitHub displays its source. The animation is 28 seconds long and demonstrates both the optional revision path and the direct path to peer scoring.

---

## 4. Architecture

```
task (tasks/*.json)  +  setup (configs/*.json)  +  protocol (protocol.json, prompts/)
                                     │
                                     ▼
cli.py                  checks pinned versions and the judging condition, writes header.json
                                     │
                                     ▼
engine/runner.py        generation 0 → J1 gate → non-author review → selection
                        → mutation + crossover → … → result.json
   ├── backends/        claude · codex · grok CLIs, OpenAI-compatible HTTP
   ├── checks/gate.py   J1: jev or a local LLM checker → checks.jsonl
   └── core/            fitness, selection, roles
                                     │
                                     ▼
run folder              header.json · events.jsonl · calls/ · checks.jsonl · result.json
   ├── resume           continues from the recorded calls
   ├── diagnose         J2 and PMID check → diagnostics/
   └── gold             gold scoring → diagnostics/gold.jsonl, summary
```

| Component | Location |
|---|---|
| Command line (`run`, `resume`, `diagnose`, `gold`) | `src/reasonlineage/cli.py` |
| Run loop, policies, call recording and replay, event log, run header, judging conditions, setup and task loading | `src/reasonlineage/engine/` |
| Fitness, selection, roles, category weights, population state | `src/reasonlineage/core/` |
| Model backends: `claude`, `codex`, `grok` CLIs and OpenAI-compatible `http` | `src/reasonlineage/backends/` |
| J1 gate, jev client, local LLM checker, combined jev rules | `src/reasonlineage/checks/` |
| J2 diagnostics, PMID check, gold scoring | `src/reasonlineage/diagnose/` |
| Packaged protocol (generations, timeouts, token caps, J1/J2 questions) and prompts | [`src/reasonlineage/protocol/`](src/reasonlineage/protocol) |
| Gold-set builders (repoDB, CT Open, synthetic, basket, bioRxiv, climate departure) | `src/reasonlineage/gold/` |
| Co-scientist pilot runner (budgets, paired ON/OFF study, expert packet export) | `src/reasonlineage/pilot/` |
| Setups, tasks, gold files | [`configs/`](configs), [`tasks/`](tasks), [`gold/`](gold) |
| Pilot protocol profiles and evidence packets | [`research/co-scientist-pilot/`](research/co-scientist-pilot) |
| Design specs, reports, archived evidence | [`specs/`](specs), [`reports/`](reports) |

---

## 5. Quick Start

### 5.1 Prerequisites

- Python 3.11 or later. The core package has no runtime Python dependencies.
- For live runs, only the backends your setup uses:
  - `claude`: the Claude Code CLI, logged in with a subscription
  - `codex`: the Codex CLI, logged in with ChatGPT
  - `grok`: the grok CLI, logged in (`grok login`)
  - `http`: an OpenAI-compatible endpoint, and a key file if it needs a key
- For the jev checker: a jev API key ([§8](#8-environment-variables-and-credentials)).

### 5.2 Install and run the offline checks

```bash
python -m pip install -e '.[dev]'
reasonlineage --help
python -m pytest -q
```

Tests exclude live model/service calls by default. The `gold` extra (`python -m pip install -e '.[gold]'`) adds numpy and scipy, which only the synthetic gold-set builder needs.

### 5.3 Choose a setup

A setup file names the panel and the checkers. See the [configuration examples](configs):

| File | Panel | Checker for public / private tasks |
|---|---|---|
| `configs/main.json` (default) | opus, gpt, grok, glm (`glm-5.3`) | jev / a local DeepSeek endpoint |
| `configs/co-scientist-pilot.json` | opus, gpt, grok, glm (`glm-5.3-flash`) | jev / a local DeepSeek endpoint |
| `configs/co-scientist-rerun.json` | gpt, grok, glm (`glm-5.3-flash`) | none |

A three-model setup with jev for public tasks looks like this:

```json
{
  "panel": [
    {"name": "gpt", "backend": "codex", "model": "gpt-6.1-sol", "effort": "xhigh"},
    {"name": "grok", "backend": "grok", "model": "grok-4.7", "effort": "xhigh"},
    {"name": "glm", "backend": "http", "model": "glm-5.3-flash", "effort": "max",
     "base_url": "https://ollama.com/v1", "family": "zai", "api_key_file": "~/.config/reasonlineage/ollama.env"}
  ],
  "checkers": {
    "jev": {"version": "jev-1.13.0", "api_key_env": "JEV_API_KEY", "api_key_file": "~/.config/reasonlineage/jev.env"}
  },
  "checker_for": {"public": "jev"},
  "concurrency_per_backend": 2
}
```

- `backend` is `claude`, `codex`, `grok`, or `http`. An `http` member also needs `base_url` and `family` (the company that made the model).
- `checker_for` maps `public` and `private` tasks to `jev` or to a local checker listed under `checkers`. jev is an outside service, and the loader rejects a setup that sends private tasks to it.
- Experiment mode refuses model names containing `latest` or `preview`. Pin versions.

### 5.4 Write a task

See the [task files](tasks). [`tasks/example-ipf.json`](tasks/example-ipf.json):

```json
{
  "id": "ipf-example",
  "question": "Which approved drug is most promising to repurpose for idiopathic pulmonary fibrosis (IPF)? Rank the candidates, and give the mechanism, the key evidence, and a validation experiment for the top pick.",
  "candidates": ["metformin", "imatinib", "sildenafil"],
  "category": "biomedical",
  "data_sensitivity": "public"
}
```

| Field | Required | Meaning |
|---|---|---|
| `id`, `question` | yes | non-empty strings |
| `candidates` | no | at least two distinct items to rank |
| `category` | no (default `biomedical`) | picks the fitness weights: `general`, `math`, `science`, `creative`, `ethical`, `coding`, `analytical`, `biomedical` |
| `data_sensitivity` | yes | `public` or `private`; picks the checker through `checker_for` |

Then start a run as shown in [§6.1](#61-start-a-run).

---

## 6. Usage in Detail

### 6.1 Start a run

```bash
# Defaults: configs/main.json, experiment mode, recuse + isolated, generations from protocol.json (3)
# Calls the models in the setup; ends with a "Done:" line naming the run folder under runs/ (ignored by Git)
reasonlineage run tasks/example-ipf.json

# Another setup, a fixed seed, another output folder
reasonlineage run tasks/example-ipf.json --config configs/co-scientist-rerun.json --seed 1 --out runs/demo

# Generation 0 only, as scripts/run_gold.sh does
reasonlineage run tasks/repodb-dev/repodb-acute-myeloid-leukemia.json --generations 0 --seed 1

# Judge the generation 0 of an earlier run under another condition
reasonlineage run TASK --gen0-from runs/RUN_FOLDER --judges self --context isolated

# Reuse every answer an earlier run recorded, with its seed and conditions
reasonlineage run TASK --replay runs/RUN_FOLDER --generations 3
```

| Option | Default | Meaning |
|---|---|---|
| `--config` | `configs/main.json` | setup file with the panel and checkers |
| `--mode` | `experiment` | `experiment` will not start unless model and jev versions are pinned, the generation count is fixed, the panel can serve the judging condition, and a checker exists when the protocol turns the J1 gate on. `exploration` checks only the judging condition. |
| `--judges`, `--context` | `recuse`, `isolated` | the judging condition ([§2.3](#23-key-design-decision-code-decides-models-write-and-judge)) |
| `--generations` | `protocol.json` (3) | with `--replay`, the replayed run's count |
| `--seed` | random | recorded in `header.json` |
| `--replay RUN_DIR` | | reuse every recorded answer, with that run's seed and conditions |
| `--gen0-from RUN_DIR` | | reuse generation 0 of a run of the same task and protocol |
| `--out` | `runs` | folder for run folders |

A run folder holds:

| Path | Contents |
|---|---|
| `header.json` | task, setup, options, protocol version and hash, CLI versions, engine commit |
| `events.jsonl` | the engine's event log |
| `calls/` | one record per model call, reused by `resume` and `--replay` |
| `checks.jsonl` | J1 checker results, when a checker runs |
| `unusable/` | outputs that could not be used, per attempt |
| `result.json` | the final summary, written when the run finishes |
| `diagnostics/` | `j2.jsonl` and `pmid.jsonl` from `diagnose`, `gold.jsonl` from `gold` |

Exit codes for `run` and `resume`: `0` done, `1` cannot start or continue, `2` stopped (fix the cause, then resume), `143` interrupted by SIGTERM or SIGHUP (resume).

### 6.2 Resume a run

```bash
reasonlineage resume runs/RUN_FOLDER
```

`resume` rebuilds the run from `header.json` and the recorded calls. It stops if the protocol files changed since the run started, and it warns if a CLI version changed.

### 6.3 Diagnose a finished run

```bash
# J2 diagnostics and the PMID check (both call outside services)
reasonlineage diagnose runs/RUN_FOLDER

# Also ask J2 whether each answer reports a clinical-trial outcome for the listed items
reasonlineage diagnose runs/RUN_FOLDER --gold-items items.json   # {"items": [{"item": ..., "outcome_date": "YYYY-MM-DD"}]}
```

- **J2** runs the task's checker over the run and writes `diagnostics/j2.jsonl`. It is skipped when no checker is available.
- **PMID check** looks up each cited PMID in PubMed and checks that the record names the item it supports. It writes `diagnostics/pmid.jsonl`.

### 6.4 Score runs against a gold file

```bash
# SET is a folder under tasks/ and gold/, e.g. repodb-dev
reasonlineage gold --gold gold/SET/gold.json runs/gold-SET/*/ \
  --out runs/gold-SET/report.json --analysis runs/gold-SET/analysis.md
```

`gold` makes no model calls. It prints a summary, writes `diagnostics/gold.jsonl` in each run folder, and, with `--out` and `--analysis`, saves the summary as JSON and the level-1 analysis as Markdown. The gold file has the form `{"tasks": {task id: {"approved": [...], "failed": [...]}}}`. A folder that is not a run, whose task is not in the gold file, whose candidates differ from the gold drugs, or whose run did not finish is left out with a warning.

### 6.5 Scripts

The jev controlled-pilot script is a dry run by default:

```bash
python scripts/run_jev_controlled_pilot.py
```

Its `--run` option executes the model/service calls described in the plan. The pilot reads `JEV_API_KEY` from the local `.env` via its credential loader; that file is ignored by Git. Provider endpoints and model names come from [`configs/co-scientist-rerun.json`](configs/co-scientist-rerun.json); protocol settings and evidence packets come from the [pilot research profiles](research/co-scientist-pilot).

| Script | What it does | Calls models |
|---|---|---|
| `scripts/run_jev_controlled_pilot.py [--run] [--out OUT]` | the 16-slot jev ON/OFF study | only with `--run` |
| `scripts/run_co_scientist_pilot.py [--run] [PROFILE FLAG]` | the bounded co-scientist pilot; profile flags: `--relaxed`, `--three-initial`, `--jev`, `--jev-combined`, `--jev-control` | only with `--run` |
| `scripts/run_gold.sh SET [OUT]` | level 1: generation 0 for every task in `tasks/SET`, then `gold` | yes |
| `scripts/run_gold_evolve.sh OUT GOLD GENERATIONS SET...` | level 2: replays finished generation-0 runs with evolution, then `gold` | yes |
| `scripts/run_gold_condition.sh OUT GOLD JUDGES CONTEXT SET...` | level 3: judges finished generation-0 runs again under one condition, then `gold` | yes |

The other scripts build gold sets (`build_*.py`), calibrate judges and jev (`calibrate_*.py`, `check_jev_combined.py`, `make_candidates.py`), compare judging conditions (`compare_conditions.py`), and check live backends (`check_backends.py`, `smoke_claude_cli.py`). The first line of each file says what it does.

---

## 7. ALS / AML pilot results

The [2026-10-09 jev ON/OFF study](reports/2026-10-09-jev-controlled.md) (Korean) covers ALS and AML across multi-model, GPT solo, Grok solo, and GLM Flash solo conditions: **16 final results**, including 13 original completions and 3 separately archived supplementary completions.

That empirical study used **three models: GPT-6.1 sol, Grok 4.7, and GLM-5.3-flash**. Opus was excluded after provider refusal, and DeepSeek and Laya were not called. The four-model overview above illustrates the method rather than that study's actual roster.

jev inspected 72 generated proposals through J1 and performed 216 J2 diagnostic assessments. **No actual J1 rewrites occurred**, so ON/OFF fitness differences do not demonstrate that jev improved results by repairing defects. The conditions also did not share identical initial proposals. Expert assessment is pending; internal fitness values are not calibrated scientific correctness probabilities or scores directly comparable with the Google co-scientist paper.

- [Purpose and methods](reports/2026-10-09-reasonlineage-purpose-and-method.md) (Korean)
- [Full self-contained evolution viewer](reports/evidence/2026-10-09-jev-controlled/run/evolution-viewer.html)
- [Candidate scores](reports/evidence/2026-10-09-jev-controlled/run/candidate-scores.csv)
- [Completed result summary](reports/evidence/2026-10-09-jev-controlled/run/completed-summary.json)
- [Anonymous expert review packet](reports/evidence/2026-10-09-jev-controlled/run/completed-review-materials/expert/README.md)
- [Evidence archive index](reports/evidence/README.md)

Download the evolution viewer HTML to browse complete responses, parent links, critiques, fitness, and jev records. When sharing the expert packet, share only the `expert` directory; the analyst mapping is stored separately.

---

## 8. Environment variables and credentials

| Variable | Read by | Purpose |
|---|---|---|
| `JEV_API_KEY` | `reasonlineage run`, `resume`, `diagnose`, when the task's checker is jev | The jev API key. The name is the default of `checkers.jev.api_key_env` in a setup. When the variable is unset, the CLI reads the file in `checkers.jev.api_key_file`. |

No other environment variable is read. Other credentials live in files:

- **`api_key_file`** on an `http` panel member or local checker: a file outside the repo that holds only the key. The program reads it and never prints it. An `http` member without one sends a placeholder key.
- **`.env`** at the root of the main checkout (shared by its worktrees): the pilot scripts read `JEV_API_KEY` from it, and the loader reads only that entry without evaluating shell code. `calibrate_jev.py --env` points to another file. Git ignores `.env`.
- **CLI logins**: the `claude`, `codex`, and `grok` backends use each CLI's own login. The grok backend runs with a temporary home that holds only the grok login, so no user configuration loads.

---

## 9. Testing

```bash
# Offline suite; tests marked `live` are deselected by default
python -m pytest -q

# A single file
python -m pytest -q tests/test_cli.py

# Live tests only: these call real models or services
python -m pytest -q -m live
```

`pyproject.toml` registers the `live` marker and sets `addopts = "-m 'not live'"`.

---

## 10. License

MIT — see [LICENSE](LICENSE).

The MIT license covers the code. Files under `gold/` derived from outside sources (repoDB, bioRxiv, NOAA weather data) remain under their sources' terms.

### References

- Google co-scientist paper: the ALS and AML research questions start from the problems it addressed. The study compares hypothesis content and approach, not scores ([purpose and methods](reports/2026-10-09-reasonlineage-purpose-and-method.md), Korean).
- Design specs (Korean): [engine design](specs/2026-09-29-engine-design.md), [co-scientist pilot design](specs/2026-10-05-co-scientist-pilot-design.md), and the other dated designs in [`specs/`](specs).
- Reports and evidence: see [§3.2](#32-how-the-gate-works) and [§7](#7-als--aml-pilot-results).
