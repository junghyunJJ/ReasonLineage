# SDD ledger — plan: plans/2026-10-03-gold-weather-level2.md

Pre-flight (plan and spec specs/2026-10-03-gold-weather-level2-design.md read; spec corrected in 82075a8 before the plan):
- Task 1 -> Task 2: produces level2(runs)["change"] = change_verdict(diffs) | {"left_out"}, keys tasks/mean/up/down/p_up/p_down/verdict/rules; Task 2's _change_summary reads exactly those keys. Clean (replayed 612 -> 621 -> 624).
- Task 1/2 -> Task 7: Task 7 reads report.json level2.change and analysis.md's "## Level 2 (evolution)" section. Clean.
- Task 3 -> Task 6: produces run_gold_evolve.sh OUT GOLD GENERATIONS SET... with OUT/left_out.txt skipping; Task 6's run_l2.sh calls that form and writes left_out.txt. Clean (simulated with a fake engine).
- Task 5 -> Task 6/7: produces gold/weather-l2/gold.json (37 ids) and check_l2.py OUT GOLD; Task 6 uses the gold file, Task 7 the checker. Clean (dry replay of all 37 already gave 592/592 replayed and the 5.3 numbers).
- Task 4 sits before the runs: it is the executing-plans final review moved forward (Tasks 5-7 add no code).
Task 1: complete (commits c480126..8a27c8e, tests: python -m pytest -q → 621 passed, 3 deselected in 18.73s)
Task 2: complete (commits 8a27c8e..00b6e82, tests: python -m pytest -q → 624 passed, 3 deselected in 18.77s)
Task 3: complete (commits 00b6e82..fd549a8, tests: python -m pytest -q → 635 passed, 3 deselected in 19.19s)
Task 5: Ruling: run Task 5 (gold file, engine check, dry replay — no model calls, no code) while the Task 4 review is in flight — it touches nothing the review covers and saves time — cost if wrong: if the review changes code, the dry replay is simply run again before Task 6.
Task 5: complete (commits fd549a8..8f26fbe, tests: python -m pytest -q → 635 passed, 3 deselected in 19.25s)
Task 5: dry replay 37/37 in 23 s: generation-0 calls not from the record 0; level 1 = 37 / 148 / 0.5270 / 97 / 0.4948 (Expected matched exactly).
Final review (Task 4, moved before the runs): fresh reviewer (fable) on 015a81e..fd549a8. Critical: none. Important: 1. Minor: 6. Committed code (verdict, output, run_gold_evolve.sh) has no defect that corrupts or silently shrinks the measurement.
Final: fixed run_l2.sh exit branch was dead code (a failure before any run folder looped without a pause, no signal) — fake-engine scenario "server stays down" RED (267 passes in 5 s, never exits) -> GREEN (3 paused retries, then "stopped: 4 failures in a row ..."); scenarios "server down once" and "a task keeps stopping" also pass; suite 635/635.
Final: fixed (re-graded from Minor 2: a duplicate finished run would enter the pre-registered verdict twice, silently) — check_l2.py now prints "A2. tasks with more than one finished run"; RED on a folder with a duplicated weather-v2-01 (no such line, B hid it as 2 tasks) -> GREEN (A2 names weather-v2-01; the 37 dry runs give none); Task 7 stops if A2 is not none; suite 635/635.
Final: Ruling: an outage longer than ~15 minutes during a run can make the in-progress task use up its 3 resumes and be left out (resume checks the HTTP members first) — the design's rule stands; the wrapper still stops at 4 left-out tasks — cost if wrong: up to 3 tasks lost to an outage, reported.
Final: Ruling: check_l2.py writes diagnostics/gold.jsonl into each run folder through score_run — the same as the gold command — cost if wrong: none (derived file).
Final: Ruling: all level-1 runs used seed 1, so later-generation call seeds repeat across tasks for the same call name — fixed by design 4.3 — cost if wrong: none for the verdict (tasks differ in prompts).
Final: Ruling: a "-2"-suffixed run folder would break the id parsing — it needs the same task to start twice in the same second, which the one-at-a-time loop cannot do — cost if wrong: one task replayed twice, which A2 now catches.
Final: Ruling: the commit trailer says Claude Opus 5.5 — that is this session's model per the current attribution instruction; the reviewer runs on fable — cost if wrong: attribution only.
Final: minor (deferred): run_gold_evolve.sh iterates the source folders, so a gold task with no source folder is not measured; the dry replay count (37) and check line B catch it before the verdict.
Final: minor (deferred): check line A counts generation-0 calls not from the record but does not name the run.
Final: minor (deferred): change_verdict compares the rounded mean; the reviewer checked every reachable mean for n <= 37 and none changes the verdict.
Final: minor (deferred): --replay does not compare the source run's protocol hash; the engine is frozen and line A catches a mismatch after the fact.
Final: minor (deferred): change.left_out is always 0 in this measurement (an answer missing a candidate stops the run in experiment mode); the counting code is right.
Task 4: complete (review + one fix pass; no code changed, plan updated in e4751a0)
Task 6: pilot weather-v2-01 passed the mechanical checks: generation-0 calls 16/16 from the record; first selection survivors ['c001', 'c002'] as computed; minutes per generation 4.7 / 5.3 / 4.0 (14 min per task; revised estimate for the other 36: about 8.5 h, up to ~15 h if generations run slow as on 2026-09-30). Correctness not looked at. Note: the engine's own "Done:" line named the best answer's author (c006 by grok, a crossover) — fitness, not correctness; nothing can be tuned from it since generation 0 is fixed.
Task 6: complete (commits e4751a0..e4751a0, tests: python -m pytest -q → 635 passed, 3 deselected in 19.44s)
Task 6: main run done at 06:52:57; 37/37 finished, 1 resume (weather-v1-14: glm's crossover unusable twice), 0 left out; glm wrote unusable crossover output on several first attempts, every one recovered.
Task 7: consistency passed exactly (A 0; A2 none; B 37 / 148 / 0.5270 / 97 / 0.4948; duplicate_tasks []; level2 tasks 37 = level1 tasks 37; engine unchanged since 015a81e).
Task 7: VERDICT (pre-registered): no change — mean d +0.0135 over 37 tasks, 4 up / 4 down / 29 unchanged, sign test p 0.637 both ways. Prediction "not gain" held. Mean correctness: gen-0 best 0.7027, final best 0.7162, gen-0 vote 0.6757.
Task 7: secondary (reported, not judged): survivors after gen 0 gpt 37 / opus 36 / glm 1 / grok 0 (as computed in advance); after gen 1 opus 33 / grok 26 / gpt 15; after gen 2 opus 34 / grok 20 / gpt 16 / glm 4. Crossover offspring survived the next selection: grok 26/37, opus 7/9, glm 4/6, gpt 4/22. Hedging words per 1,000 chars: gen 0 0.53, gen 1 1.35, gen 2 1.53, gen 3 1.27. Mean fitness by generation 0.585 / 0.637 / 0.639 / 0.640.
Task 7: post-hoc descriptives: the final best keeps generation 0's best top pick in 32/37 tasks; a fully correct answer was in gen 0 and in the final population in 22 tasks, lost in 8, gained in 1, never in 6; when a fully correct answer survived to the end it was always the fitness-best (0 cases otherwise).
Task 7: complete (commits e4751a0..e4751a0, tests: python -m pytest -q → 635 passed, 3 deselected in 19.16s)
