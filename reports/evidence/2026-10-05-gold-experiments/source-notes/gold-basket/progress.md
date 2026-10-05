# SDD ledger — plan: plans/2026-10-02-gold-basket.md

Setup: original checkout /common/jungj2/project/ReasonLineage, branch gold-basket (on gold-biorxiv, not main), start 3c4544d. Spec: specs/2026-10-02-gold-basket-design.md. Executor: Native (executing-plans), chosen by the user with the runs approved. TDD skill loaded earlier this session.

Pre-flight:
- T1 -> T2: produces price, ITEMS, STORES, BANDS / consumed by winner, flipping, margin — match.
- T2 -> T3: produces winner, flipping, margin / consumed by draw's band filter — match.
- T3 -> T4: produces draw (basket, stores, receipts, margin, flipping, winner) and printed / consumed by make_task, build — match.
- T1 -> T4: produces QUESTION, won, STORES, build.shuffled / consumed by question, make_task, build — match.
- T4 -> T5: produces basket.build, basket.BasketError / consumed by scripts/build_basket.py — match.
- T5 -> T6, T7: produces the build script / consumed by the calibration and main sets — match.
Task 1: complete (commits 3c4544d..bd2139f, tests: python -m pytest -q tests/test_gold_basket.py → 14 passed in 0.06s)
Task 2: complete (commits bd2139f..c0dd61b, tests: python -m pytest -q tests/test_gold_basket.py → 24 passed in 0.07s)
Task 3: complete (commits c0dd61b..a5eafcd, tests: python -m pytest -q tests/test_gold_basket.py → 28 passed in 0.74s)
Task 4: complete (commits a5eafcd..fbd817a, tests: python -m pytest -q tests/test_gold_basket.py → 36 passed in 0.90s)
Task 5: complete (commits fbd817a..47040ac, tests: python -m pytest -q tests/test_build_basket_script.py → 5 passed in 0.30s)
Final review: fresh reviewer (general-purpose, fable) on 023564b..47040ac — "With fixes": 2 critical, 5 important, 4 minor; the arithmetic, the leakage guard and determinism were verified by hand on a generated task.
Final: Ruling: C1 (the prompt did not state the pricing conventions the gold depends on, and the generator kept hard tasks precisely because an unstated convention decided the winner — 45% of that band) — amended spec 4.2/4.4 and the question text rather than asking first: the alternative measures an arbitrary convention, the fix only states what the code already does, and the user can still object before any run; re-measured after the fix, no band is decided by percent_before_coupon alone except 11% of easy, which is now a misreading of a stated rule — cost if wrong: the question is one paragraph longer
Final: fixed C1 — test_the_question_states_the_conventions_the_answer_depends_on RED→GREEN
Final: fixed C2 the letter schedule depended on the task count, so extending a set rewrote measured tasks' gold in silence — letter_for() takes the task's own index, three tasks per block; test_extending_a_set_leaves_the_earlier_tasks_and_their_gold_untouched[6,9,11] RED→GREEN
Final: fixed I3 percent_before_coupon left the "after the coupon" threshold at the after-percent-only amount — test_reading_the_percentage_first_also_moves_the_after_coupon_threshold RED→GREEN
Final: fixed I4 percent_on_delivery let the fee open the percentage threshold — test_the_delivery_fee_never_opens_the_percentage_threshold RED→GREEN
Final: fixed I5 tests/test_gold_basket.py carried a byte-for-byte duplicate of its first 81 lines (the plan's Task 1 block did too) — removed from both; the duplicate shadowed 7 tests
Final: fixed I6 the stores were printed in draw order, not letter order — test_the_question_lists_the_stores_in_letter_order RED→GREEN
Final: fixed I7 generation.json recorded only the flipping names, not what each misreading picks — test_the_record_says_which_store_each_misreading_picks RED→GREEN
Final: suite 560/560 after the fix pass
Final: minor (deferred): M1 the conditional percentage draws 3-8% where spec 4.2 says 5-10% for that form
Final: minor (deferred): M2 a tie for cheapest under a misreading resolves to the first index and may count as a flip (2 of 300 hard tasks)
Final: minor (deferred): M3 draw_rules' local `goods` is the shelf total before bundles while price()'s `goods` is after them; a confusing name
Final: minor (deferred): M4 the band-failure message names the failing task id but not how many tasks were filled (spec 7)
Final: Ruling: declined-to-judge — level-1 thresholds and the band-selection rule (inherited specs), the item list and price draw (spec 4.1), the analytical category's weights and load_task (engine), run_gold.sh skip/resume (unchanged; C2 was the real interaction and is fixed), the duplicated BANDS tuple in the script (commented), gb.html and the trailer (not in the diff), the hard band's ~0.9% acceptance rate (2,000 tries gives a failure near 1e-8) — each stands as it is — cost if wrong: none for the measurement
Task 6: Ruling: the review's fixes changed what the bands keep, so the calibration sets were rebuilt after the fix pass, before any run — cost if wrong: none; no run had started
Task 6: Step 4 — calibration finished (6 tasks, 39 min): share_correct 1.00 in easy, medium AND hard, 0 pairs each. The band rule says stop and decide with the user (no band in 0.375-0.75).
Task 6: evidence of why: in the hard band (margin 0.3%) every answer named the exact won totals of all three stores (10 of 12 receipts quoted exactly, 402-775 words). The models do the bookkeeping exactly, so stating the conventions removed the only thing they could get wrong. This is the calculation ceiling the synthetic hidden-law set hit, in a second form.
Task 6: side finding: opus wrote and judged these basket tasks without a single refusal at the same time it was still refusing biorxiv-v1-01. So the refusals are specific to the biomedical content, not a global provider state; the content became refusable at some point today (tasks 9 and 10 ran fine earlier).
