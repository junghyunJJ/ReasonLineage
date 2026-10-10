# SDD ledger — plan: plans/2026-09-30-gold-v0.md

Setup: worktree .claude/worktrees/gold-standard-v0, branch gold-v0, start 00ea511. Spec: specs/2026-09-30-gold-v0-design.md. Executor: Native (executing-plans). TDD skill content already loaded in this session.

Pre-flight:
- T1 -> T3: produces repodb.tested_drug(interventions, name_drugs) / consumed by ctopen.candidates via name_drugs — match.
- T2 -> T3: produces ctopen.SourceError / consumed for missing FIELDS — match.
- T3 -> T4: produces candidate dicts (+conditions, phases, fetch_error via attach) / consumed by ctopen.build — match.
- T1-T4 -> T5: drug_namer, load_set, candidates, attach, build, SETS, SourceError, ReviewError (+ existing repodb.load_rows, trials.fetch_trials, both present) — match.
- T5 -> T7: scripts/build_ctopen.py — match.
- T1-T6 -> T8: all of the above — match.
Task 1: complete (commits 00ea511..06f00ed, tests: python -m pytest tests/test_gold_repodb.py -q → 27 passed in 0.05s)
Task 2: complete (commits 06f00ed..c8d64d3, tests: python -m pytest tests/test_gold_ctopen.py -q → 7 passed in 0.03s)
Task 3: complete (commits c8d64d3..2c7cd6a, tests: python -m pytest tests/test_gold_ctopen.py -q → 24 passed in 0.05s)
Task 4: complete (commits 2c7cd6a..dfcc7f2, tests: python -m pytest tests/test_gold_ctopen.py -q → 34 passed in 0.09s)
Task 5: Ruling: the plan creates scripts/build_ctopen.py without a file mode — made it executable (chmod +x) like the prototype and its sibling build_repodb_dev.py, since it has a shebang — cost if wrong: one mode bit
Task 5: complete (commits dfcc7f2..5fe5a4f, tests: python -m pytest tests/test_build_ctopen_script.py -q → 3 passed in 0.27s)
Task 6: complete (commits 5fe5a4f..5a1a7d2, tests: python -m pytest -q → 361 passed, 3 deselected in 7.50s)
Task 7: Ruling: spec 7 says rehearsal files sit in a temporary folder outside the repo; the plan uses runs/ctopen-rehearsal/ — kept the plan's folder: runs/ is git-ignored (.gitignore:36), so nothing enters the repository (the spec's intent) and the files stay where the user can read them — cost if wrong: they must be moved before this worktree is removed, like runs/gold-dev
Task 7: rehearsal numbers — summer-2025: 30 candidates (17 MET, 13 NOT MET), review keep 14 (8 MET, 6 NOT MET) / drop 16 (rule 2: 15, rule 1: 1), build 3 tasks, rebuild from the same inputs identical; winter-2025: 38 candidates (20 MET, 18 NOT MET). No model calls, nothing committed.
Task 7: complete (commits 5a1a7d2..5a1a7d2, tests: python -m pytest -q → 361 passed, 3 deselected in 7.55s)
Task 8: stopped at Step 1 as planned — CT Open datasets/ holds only Summer_2025, Winter_2025 and Train_2025 parts; main head is still cc78ff33 (2026-09-06). Steps 2-5 wait for the 2026 release.

Final review: fresh reviewer (general-purpose, opus) on 287f3a6..5a1a7d2 — "with fixes": 0 critical, 5 important (I1, I2 code; I3-I5 plan/spec), 8 minor.
Final: fixed I1 pooled-arm entries (meta_label no_distinguishable_arm; the tuple names only the first pooled arm) — test_trials_that_are_left_out[changed9] RED→GREEN, suite 365/365; 2025 candidates byte-identical (30, 38)
Final: fixed I2 display_name and why not checked (trailing space → score_run mismatch; uppercase → disease overlap in a task; blank why passed) — test_review_rules_are_enforced (3 new cases) RED→GREEN, suite 365/365; rehearsal rebuild identical
Final: Ruling: I3 the question shows raw arm labels ("Group A vs Group B") and candidates.json has no per-arm details — code stands: spec 4.4 fixes the question format and 4.2 the candidates fields, so changing them is the user's design call before Task 8 — cost if wrong: some 2026 questions show vague arms and the review can miss designs like a delayed start; no wrong gold
Final: Ruling: I4 CT Open's MET means a significant improvement over the comparator, while the question asks which trial is "most likely to meet its primary endpoint" — code stands: the question is the approved spec 4.4 wording; rewording it or dropping non-inferiority/equivalence trials is the user's call before Task 8 — cost if wrong: a non-inferiority trial in a 2026 task is labelled against the question's meaning
Final: Ruling: I5 the plan's review view prints MET/NOT MET — not changed now (no code involved); a blind Task 8 review fits spec 4.3 ("not choosing by results") and goes to the user with the other Task 8 decisions — cost if wrong: borderline review calls may lean on the label
Final: Ruling: rehearsal review standards (which approvals count, how strict "same disease" is, population vs disease, route) — the rehearsal review stays as is (not a measurement, not committed); the four standards go to the user as a spec 4.3 update before Task 8 — cost if wrong: inconsistent keeps and drops in the 2026 review
Final: Ruling: declined-to-judge items, each kept as the spec or plan prescribes — (1) CT Open report dates as first public report: spec 4.2, J2 ② is the backstop; (2) 2026-07-01 vs GLM-5.3's unknown cutoff: spec §10 defers; (3) greedy pairing may build fewer tasks than optimal matching: spec 4.4 prescribes it, the rehearsal reached the maximum (3); (4) one drug twice in a task for different diseases: spec asks only for distinct diseases; (5) add-on trials whose tested arm lists a non-repoDB drug are dropped: dev rule reused, mostly the outside drug is the one tested; (6) positional task ids and the runs/gold-SET default: spec prescribes, side effects deferred as M5/M7; (7) "phase 2/phase 3" format: cosmetic; (8) non-atomic cache write, no retry: mirrors the repoDB loader, sha256 catches a partial file; (9) a rare pickle opcode surfaces as ValueError: sha256 is checked first and the file is still refused; (10) two shuffle keys: both derive from the set name, plan prescribed; (11) scoring/level-1/J2 code: unchanged here; (12) medical accuracy of each approval claim: rehearsal only, covered by the review-standards decision; (13) spec §1 "after" vs §4.2 "on or after": code uses "on or after", same result given the cutoffs, align at the next spec edit; (14) "review.json breaks the rules:" prefix for stale task files: mirrors the sibling script and says what to do — cost if wrong: at most a task fewer per window or a less clear message; no wrong gold
Final: minor (deferred): M1 no test for the candidates step of build_ctopen.py
Final: minor (deferred): M2 the build test checks correctness, not score_run's candidate-set check
Final: minor (deferred): M3 a missing or malformed candidates.json/review.json gives a raw traceback
Final: minor (deferred): M4 the stale-file check covers task files, not items/
Final: minor (deferred): M5 positional task ids + skip by id: rebuilding a set after runs exist skips changed tasks and reports mismatch
Final: minor (deferred): M6 run_gold.sh does not check gold/SET/gold.json before the model calls
Final: minor (deferred): M7 the dev set's default output moved to runs/gold-repodb-dev; its finished runs are in runs/gold-dev (pass that as OUT, or all 7 tasks run again)
Final: minor (deferred): M8 the endpoint shown for several primary endpoints is picked by sorted text; undocumented
Final: Ruling: kept this plan's workspace instead of deleting it after the clean fix pass — Task 8 is still pending and resumes from this ledger — cost if wrong: a git-ignored folder stays in the worktree
Post-plan (2026-10-01, branch gold-v0-rules): user approved 4 review changes — question asks for significant improvement over the comparator; blind review via review_sheet.md; optional comparison text; review standards in spec 4.3. Task 8 Step 3 in the plan now uses them. Rehearsal re-review under the new rules: 2 tasks.
