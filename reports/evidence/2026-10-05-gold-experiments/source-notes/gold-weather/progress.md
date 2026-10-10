# SDD ledger — plan: plans/2026-10-03-gold-weather.md

Pre-flight (shared-interface rows, plan read, spec specs/2026-10-03-gold-weather-design.md read):
- Task 1 -> Task 2: produces REGION_OF/MONTHS/MEASURES/SourceError + pool format "<month>:<measure>" -> {state: departure}; Task 2 consumes the same names. Clean (the plan's code was replayed on a fresh copy of gold-weather: 560 -> 568 -> 587 -> 596 -> 605 passed).
- Task 2 -> Task 3: produces choose() items {month, measure, states, departures, regions, margin}; Task 3's make_task reads exactly those keys. Clean.
- Task 3 -> Task 4: produces build(set, band, count, pool, source, tasks_dir, gold_dir, exclude) and triples_of(gold_dir); the script calls both with those arguments. Clean.
- Task 4 -> Task 5/6: produces `fetch` and `build SET --band --tasks [--exclude-set]`; the run tasks call that form. Clean.
- Task 6 -> Task 7: produces runs/gold-weather-v1 and gold/weather-v1/generation.json; Task 7's snippet reads month/measure from the record. Plumbing checked against runs/gold-basket-calib-easy (score_run + level1 over a filtered subset works).
Task 1: complete (commits bbf4e93..b4fccd9, tests: python -m pytest -q → 568 passed, 3 deselected in 16.93s)
Task 2: complete (commits b4fccd9..ed7ed49, tests: python -m pytest -q → 587 passed, 3 deselected in 17.14s)
Task 2: note: the RED run printed `has no attribute 'usable'` first; the brief quoted `choose`. Both are in the 19 failures (19 failed, 8 passed as Expected).
Task 3: complete (commits ed7ed49..0c82f53, tests: python -m pytest -q → 596 passed, 3 deselected in 17.63s)
Task 4: complete (commits 0c82f53..3578b12, tests: python -m pytest -q → 605 passed, 3 deselected in 18.93s)
Task 5: Ruling: the plan/spec said STATE_IDS = 1~50, but NCEI id 49 is unused (404, fatal to fetch) and 50/51 are Alaska and Hawaii with base periods 1925-2000 and 1991-2000 — not the 1901-2000 normal the question names. Changed to 1~48 (the contiguous states, 1 Alabama to 48 Wyoming), pinned by test_the_state_ids_are_the_48_contiguous_states (RED->GREEN), and corrected spec 4.1 and the plan. Cost if wrong: a contiguous state missing from the pool would shrink supply; all 48 fetched, so none is.
Task 5: complete (commits 6541685..6541685, tests: python -m pytest -q → 606 passed, 3 deselected in 19.07s)
Task 5: bands easy 0.375 / medium 0.500 / hard 0.125 -> picked medium (closest to 0.6 inside 0.375-0.75). First set that is not at the ceiling; pairs 9/8/3 over 2 tasks each.
Task 6: complete (commits 6541685..438f702, tests: python -m pytest -q → 606 passed, 3 deselected in 18.76s)
Final review: fresh reviewer (fable) on f71ee07..438f702. Critical: none. Important: 4. Re-graded by effect: finding 1 (false premise + unstated unit) is the most severe — it made 3 of 20 measured tasks unanswerable as asked; 2, 3, 4 stand as Important. Five minors deferred.
Final: fixed 1 (false premise + unit) — test_usable_refuses_a_triple_with_no_state_above_its_normal and test_the_question_names_the_unit_and_the_convention RED->GREEN, suite 612/612.
Final: fixed 2 (silent overwrite of a measured task) — test_build_stops_when_a_task_it_builds_would_change RED->GREEN, suite 612/612.
Final: fixed 3 (set not rebuildable from the repository) — test_load_index_reads_the_committed_readings RED->GREEN plus test_changed_readings_say_to_fetch_again; dropped the absolute cache path from gold/weather/pool.json; suite 612/612.
Final: fixed 4 (test gap) — test_the_values_come_from_the_month_and_measure_the_task_names; it passed on correct code, so it was verified by injecting a wrong-bucket read into choose() (test failed) and reverting; suite 612/612.
Final: Ruling: weather-v1 and the calibration sets keep the task files and gold they were measured with, although the question template and the filter have since changed. The pre-registered rule forbids changing a set after seeing its results, so the v1 verdict stands on the text the models actually answered; the fix applies to the next set. Cost if wrong: v1's three false-premise tasks stay in the published 20-task verdict (no signal), and the auxiliary 17-task number is post-hoc, so it cannot replace it.
Final: minor (deferred): the index and gold `source` record no fetch date (NCEI revises recent months; the sha256 still pins the content exactly).
Final: minor (deferred): weather.py:31 comment says the region rule excludes Alaska, but since Task 5 the id range excludes it first.
Final: minor (deferred): spec 4.3 and margin()'s docstring say precision 0.1, but precipitation departures carry 0.01 (the 0.3 inch floor's rationale is loose).
Final: minor (deferred): fetch() drops a reply whose title or month key is unreadable without naming which state on stderr.
Final: minor (deferred): generation.json's `winner` field is not in the spec's list (harmless, for human checking).
v2 (pre-registered in spec section 11, commit 82296a4, built 015a81e): 20 tasks, verdict "no signal" — share 0.500, pairs 45, concordance 0.356 (concordant 16 / discordant 29; the reverse direction's sign test p = 0.036). The post-hoc 0.615 from v1 did NOT replicate; the pre-registered prediction's second branch holds (fitness does not track correctness). Pooled v1+v2: 40 tasks, 110 pairs, concordance 0.436, reverse p = 0.107 — indistinguishable from chance, leaning negative.
v2 by judge: grok 0.71 (24 pairs), gpt 0.34, opus 0.27, glm 0.24. Pooled: grok 0.684 (57), gpt 0.476, glm 0.413, opus 0.373. One judge of four discriminates; the rest are at or below chance.
v2 by author: grok 0.80, gpt 0.65, glm 0.65, opus 0.62. grok is again the most accurate author and again receives the lowest fitness (0.522 vs opus 0.638). Fitness gap correct-vs-wrong collapsed to +0.002 (v1: +0.027); opus's own gap is -0.002.
