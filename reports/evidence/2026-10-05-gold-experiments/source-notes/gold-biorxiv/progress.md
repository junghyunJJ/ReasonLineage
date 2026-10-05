# SDD ledger — plan: plans/2026-10-02-gold-biorxiv.md

Setup: original checkout /common/jungj2/project/ReasonLineage, branch gold-biorxiv (on gold-synth, not main), start 538b061. Spec: specs/2026-10-02-gold-biorxiv-design.md. Executor: Native (executing-plans), chosen by the user. TDD skill loaded earlier this session.
Setup: the user pre-approved the model-calling runs (Tasks 8, 10); the only stops are the two reviews (Task 7, Task 9) and the pilot rule.

Pre-flight:
- T1 -> T2..T4: produces the pool functions, SourceError, CATEGORIES / consumed by sentences, candidates, build — match.
- T2 -> T3: produces sentences, split_problems, alteration_problems / consumed by make_candidate — match.
- T3 -> T4: produces LETTERS and the candidate dict (status, context, result, reversed, altered) / consumed by review_sample, build — match.
- T1..T4 -> T5: produces the biorxiv API / consumed by scripts/build_biorxiv.py — match.
- T6 -> T8, T10: produces reasonlineage gold --analysis and run_gold.sh writing analysis.md / consumed by the runs — match.
- T5 -> T7, T9: produces the build script / consumed by fetch, candidates, build — match.
Task 1: complete (commits 538b061..374f77c, tests: python -m pytest -q tests/test_gold_biorxiv.py → 15 passed in 0.04s)
Task 2: complete (commits 374f77c..fadae9a, tests: python -m pytest -q tests/test_gold_biorxiv.py → 28 passed in 0.05s)
Task 3: complete (commits fadae9a..c802b9e, tests: python -m pytest -q tests/test_gold_biorxiv.py → 36 passed in 0.07s)
Task 4: complete (commits c802b9e..c317e56, tests: python -m pytest -q tests/test_gold_biorxiv.py → 46 passed in 0.10s)
Task 5: complete (commits c317e56..d842355, tests: python -m pytest -q tests/test_build_biorxiv_script.py → 7 passed in 0.56s)
Task 6: complete (commits d842355..bef08eb, tests: python -m pytest -q tests/test_gold_diagnose.py tests/test_cli.py tests/test_gold_scripts.py → 51 passed in 1.14s)
Final: Ruling: the whole-plan review runs after Task 6 and before the model-calling tasks, as the plan's Global Constraints say; Task 7's fetch and pilot candidates (local DeepSeek, no cost) run meanwhile and are redone if the review changes generation — cost if wrong: one more 5-minute candidates run
Final review: fresh reviewer (general-purpose, fable) on 302652e..bef08eb — "No": 2 critical, 3 important, 6 minor; filters, dedupe, determinism and the _counted refactor verified on the real cache.
Final: fixed C1 a review drop deadlocked candidates/build — test_a_paper_dropped_in_review_is_replaced_and_the_set_builds (script) + test_a_paper_dropped_in_review_stays_on_record_and_the_next_one_is_added RED→GREEN
Final: fixed C2 API markup ({beta}, [&ge;], O_LI, glued headings) could tell the verbatim real result from the rewrites — test_api_markup_is_decoded_to_the_characters_authors_wrote, test_abstracts_with_list_figure_heading_or_unknown_markup_are_left_out[4], test_rewrites_are_stored_with_plain_spacing RED→GREEN
Final: fixed I3 a paper withdrawn in a later version stayed in the pool — test_a_paper_withdrawn_in_a_later_version_is_left_out_of_the_pool RED→GREEN
Final: fixed I4 the splitter under-split after digits ("2D.", "κB.") and before lowercase/Greek starts — test_sentences_end_after_a_digit_or_a_lowercase_start_but_not_after_initials RED→GREEN; Ruling: one test sentence first used "loss of X. mTOR", which the accepted initials rule cannot split; changed to "loss of Lgr5." — cost if wrong: none, the reviewer named single-capital ends as acceptable
Final: Ruling: I5 (the real result at A in 4 of 5 pilot tasks) — fixed rather than asked: no result has been seen, the spec's intent is an unbiased fixed shuffle, and a balanced set-level assignment keeps it fixed and reproducible; spec 4.7 updated — test_the_real_result_is_spread_evenly_over_the_letters[1,4] RED→GREEN, suite 506/506 — cost if wrong: none for the gold; letters differ from the per-task shuffle
Final: minor (deferred): M1 format_analysis prints "?" for correctness other than 1/0.5/0 (repodb-dev's multi-approved gold) against a ✓/½/✗ legend
Final: minor (deferred): M2 level1 compares runs by equality, not identity, so a run directory passed twice is no longer listed under set_aside
Final: minor (deferred): M3 the page cache is keyed by cursor only; a future window change would reuse stale pages
Final: minor (deferred): M4 a twice-rejected rewrite records a generic reason, not the alteration_problems text
Final: minor (deferred): M5 about 4% of abstracts open their results with a "Results:" heading; reviewers should look for it
Final: minor (deferred): M6 the review sheet does not flag a surface difference (non-ASCII) between the real result and the rewrites
Final: Ruling: declined-to-judge — absolute full_pool path, DeepSeek checking its own rewrites, published as a fetch-time snapshot, June-submitted DOIs posted in July, casefold in alteration_problems, species-name non-splits, method+result in one sentence, abstracts stored in candidates.json — each is a spec decision or repository policy — cost if wrong: none for the gold
Task 7: pool rebuilt from the cache after the review fixes: 4,270 papers (markup residue and later withdrawals left out); pilot candidates 5 kept, 0 dropped, no markup left; committed; waiting for the user's review (the plan's first stop)
Task 7: complete (commits bef08eb..8acb037, tests: python -m pytest -q tests/test_gold_biorxiv.py tests/test_build_biorxiv_script.py → 69 passed in 0.67s)
Task 8: Step 1 built the pilot (5 tasks; real letters B, B, A, A, C) and committed 3a315ff; review.json records the user's 'keep all'
Task 8: pilot finished (all 5 tasks, ~8-10 min each, 1 transient failure retried): share_correct 0.95 (19/20), 3 pairs, concordance 1.00 (sign test p 0.125) -> pilot rule: ceiling, stop and decide with the user. Diagnosis from the answers: models reject the rewrites because they contradict the background (e.g. pilot-04: 'GABAergic' vs the background's 'monoaminergic centers'; opus and glm cite it), confidence ~0.94 for the real result — consistency with the shown context, not prediction of the finding.
Task 8: Ruling: the user chose option 1 after the pilot ceiling — rewrites must not contradict the background; a background check (DeepSeek with the context, 3 rotations, drop at 3 of 3) follows the wording check; --exclude-set repeats; RED→GREEN (4 tests), suite 509/509; spec 4.4, 4.5, 5.1 and a plan addendum record it; a second pilot biorxiv-pilot2 excludes the first pilot's papers — cost if wrong: another pilot (~1 h) and fewer usable papers
Task 8: biorxiv-pilot2 candidates: 5 kept, 0 dropped (3.4 min); committed; waiting for the user's review
Task 8: biorxiv-pilot2: the user kept all 5; built and committed; run started
Task 8: biorxiv-pilot2 finished: share_correct 0.75 (15/20), 3 pairs, concordance 1.00 -> pilot rule: go to the main set. Note: in pilot2-04 all four answers chose the same wrong result (no pairs there); pairs may be scarce in the main set.
Task 8: complete (commits 8acb037..956823a, tests: python -m pytest -q tests/test_gold_biorxiv.py tests/test_build_biorxiv_script.py → 72 passed in 0.67s)
Task 9: biorxiv-v1 candidates: 20 kept, 6 dropped (2 wording, 3 background, 1 unusable rewrites); committed; waiting for the user's review of the 5-paper sample
Task 9: complete (commits 956823a..0a57089, tests: python -m pytest -q tests/test_gold_biorxiv.py tests/test_build_biorxiv_script.py → 72 passed in 0.70s)
Task 10: the user kept all 5 sampled papers; built 20 tasks and committed; main run started
Task 10: Ruling: biorxiv-v1-11's paper was refused by one provider's safety classifier (5 failed calls, all gpt via codex; opus, grok and glm judged the same text) — on the user's instruction the paper is dropped and replaced rather than retried or reworded; its unfinished run was moved to runs/biorxiv-v1-flagged/, the DOI is in review.json drop with a reason, candidates added one immunology paper (21 kept), and the rebuild changed only tasks 11 and 12 (01-10, already run, verified identical) — cost if wrong: the set's immunology papers shift by one; no result was seen for the dropped task
Task 10: spec 7 now records the rule: a paper any panel member's provider refuses is dropped and replaced, never retried or reworded
Task 10: the replacement immunology paper was refused too, this time by opus (claude CLI) at the write step — so the refusals are not codex-specific. Dropped and replaced again (2 drops recorded in review.json); rebuild changed only tasks 11-12 and tasks 01-10 stay identical.
Task 10: probes — a first probe ('Reply with {"ok": true}' + the text) refused 8 of 8 next immunology papers AND the already-measured tasks 09/10, so that framing is not a faithful screen. With the engine's real author prompt: tasks 11 and 12 are refused by opus, accepted by gpt. So the two current immunology replacements are genuinely unusable, and a faithful pre-screen needs the real protocol prompts.
Task 10: of 4 immunology papers tried for slots 11-12, 3 were refused by a provider (1 gpt, 2 opus); only immunology tasks 09 and 10 completed. Waiting for the user's choice: finish with immunology at 2 (18 tasks), keep churning for 4, or re-run as 4 fields x 5.
Task 10: STOP and reconsider — the refusals are not about the papers. Control probes with the engine's own author prompt now get "REFUSED by opus" for biorxiv-v1-01, biorxiv-v1-09 and biorxiv-pilot2-04, all of which the same panel wrote and judged successfully earlier today (a plain arithmetic prompt is still accepted, so the CLI works). 6 of the 8 unrun tasks were refused in the same window, across three fields.
Task 10: Ruling: reverted the paper churn to HEAD (20 tasks, one drop from the real gpt refusal) instead of replacing papers on pre-screen evidence — that evidence is invalid while the provider refuses known-good tasks, and dropping good papers would bias the set; the two pre-screen drops and the immunology limit are undone — cost if wrong: if some of those papers really are refused, the run will stop on them and the driver's drop-and-replace handles it
Task 10: kept the code from the attempt (build --limit FIELD=N, letters drawn for the declared size so a short field cannot change a measured task; tests 511 pass) — it is the fix for a real defect found on the way
Task 10: wait_then_run.sh now probes biorxiv-v1-01 every 30 min (one call) and starts the run as soon as it is accepted, up to 8 hours
Task 10: the user approved the arXiv spec (specs/2026-10-02-gold-arxiv-design.md, commit e197ff1) and asked for its implementation plan once the bioRxiv main run finishes; the refactor it needs must wait for the run so the engine code stays fixed mid-measurement
Task 10: the provider refusal has held for 7 checks over ~3 hours (15:32-18:36); the watcher gives up after 16 checks (~23:30). bioRxiv v1 stands at 10 of 20 tasks measured.
