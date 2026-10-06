# Co-Scientist pilot implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline, test-driven-development for implementation, verification-before-completion, and one independent code review before live execution. The user approved the written design and requested immediate continuation.

**Goal:** Run the approved ten-method/case pilot within four hours and export reproducible public traces, independent evaluation, literature checks, and anonymous expert materials.

**Architecture:** Reuse the existing Runner, selection/state, protocol loader, backends, and CallRecorder. A pilot-only Runner adapts single-model revisions and strict one-hypothesis writing. Budgeted backends track all usage and redact private provider fields. A study driver schedules isolated runs, then exports blinded material and four held-out reviews. Default engine behavior remains unchanged.

**Tech stack:** Python standard library, existing ReasonLineage engine, pytest, existing CLI/Ollama authentication.

**Spec:** `specs/2026-10-05-co-scientist-pilot-design.md`.

## Global constraints

- Cases: ALS and AML; methods: ReasonLineage, GPT, Opus, Grok, GLM Flash; one complete run each.
- Generation panel/efforts: the pinned `configs/co-scientist-pilot.json`; independent evaluator `deepseek-v4.1-flash`.
- Same frozen case evidence; 4 initial candidates; 3 critics per candidate; 3 rounds; one hypothesis per candidate.
- Per run: 40 backend attempts, 400,000 reported total tokens, 1,200 seconds; no controller retries.
- Shared live deadline: 14,400 seconds; generation allowance 12,000 seconds; independent evaluation reserved remainder.
- Timeouts at most 300 seconds and remaining deadlines; HTTP max output 32,768; review max output 16,384.
- No J1/checker calls, no generator search, no expert contact, no credentials/private reasoning in persisted records.
- Expert preferences remain pending; internal fitness/LLM ratings are not biological ground truth.
- No changes to default protocol, original main, measured tasks, or previous runs.

## Review focus

- Cached input must be accounted for without double-counting reasoning or cache subsets.
- A cutoff, unknown consumption, failure or malformed output must not become a completed final proposal.
- Fresh critic replicas must produce three separately recorded calls, not one cached response.
- Anonymous materials must exclude model/method/stage mapping and automatic evaluation scores.
- Deadline cancellation and process shutdown must prevent additional dispatch; preserve already completed data.

## Task 1: Usage, budget and public-record boundary

Files: `src/reasonlineage/pilot/budget.py`, `tests/test_pilot_budget.py`.
Interfaces: normalize provider usage; reserve calls against token/deadline limits; wrap existing `ModelBackend.complete` while retaining only public response/data and safe usage metadata.

- [x] Write regression tests for separate cache accounting, inclusive totals, missing/invalid usage, call/token/time cutoff, no retries, and private-field/credential redaction.
- [x] Run tests and observe meaningful failure before implementation.
- [x] Implement the minimal budget and metering layer; run targeted tests and the complete offline suite.
- [x] Commit verified work and record results in the task ledger.

## Task 2: Case data, protocol and controlled runner

Files: `research/co-scientist-pilot/protocol/`, `src/reasonlineage/pilot/run.py`, `tests/test_pilot_run.py`.
Consumes: metered backends and budgets from Task 1; existing Runner, EventLog, CallRecorder, corpus and config.
Produces: method/case header, 40-call complete traces, initial best and final best, budget/failure status with no live evaluation feedback.

- [ ] Test actual fake-backed multi-model and solo runs: 10 candidates, 30 recorded critics, 40 calls; solo has no crossovers and fresh critic names.
- [ ] Test strict output rejection without realignment/retry, input/config fingerprint isolation, public records and partial failure.
- [ ] Observe failures, implement pilot-only overrides and a separate protocol, verify targeted tests and full suite.
- [ ] Commit and ledger.

## Task 3: Study, anonymous export and independent review

Files: `src/reasonlineage/pilot/review.py`, `src/reasonlineage/pilot/study.py`, `scripts/run_co_scientist_pilot.py`, `tests/test_pilot_review.py`, `tests/test_pilot_study.py`.
Consumes: Task 2's status/results; Task 1's global metering; pinned corpus/config.
Produces: dry-run plan; ten isolated generation slots; anonymous proposals, pairs and analyst-only mapping; four reversed-order held-out reviews; separate citation audit; summary and expert packet.

- [ ] Test anonymous identity isolation, duplicate reuse, initial/final pairing, response ID validation and bibliography checks.
- [ ] Test dry-run without backend calls, refuse output reuse, bounded partial scheduling and total call accounting using real runners with fake services.
- [ ] Implement after failing tests; run full offline suite and CLI dry-run.
- [ ] Commit; obtain one read-only independent review; fix material findings with regression tests.

## Task 4: Live pilot and reporting

- [ ] Freeze commit/config/protocol/corpus IDs; validate available HTTP model IDs without generation calls.
- [ ] Start the supervised four-hour live batch, collect progress, and honor refusal/cutoff without retries.
- [ ] Verify complete/failed/unstarted slots and independent-review status; check cited literature/approval facts where possible.
- [ ] Deliver expert-only anonymous packet and a separate analyst report with usage comparability and outstanding expert judgments.

Source/read-only implementation preparation is outside the four-hour live clock. A documentation change does not reopen the agreed interview decisions.
