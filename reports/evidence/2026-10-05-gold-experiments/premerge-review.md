# Independent pre-merge review

Reviewed range: `c949df9..697a9ff`. Review was read-only; no real models or services were called.

Verdict: **Ready to merge for the authorized local closeout.** No critical or important blocker affects preservation or the reported measurements.

The reviewer independently verified all 7,740 archive entries against originals and the inventory, both recorded archive/inventory checksums, 10 copied progress/check notes, 16 result-source checksums, and the L2/L3 aggregate results calculated again from raw events. Existing evidence records 651 passed and 3 live tests deselected. The report distinguishes correctness from fitness, limits the weather interpretation, and marks bioRxiv incomplete and arXiv unrun.

## Important before future reuse

`scripts/run_gold_condition.sh:52` skips existing results by task ID without checking their `judges/context`. Reusing an output folder for a different condition can mix measurements. The saved L3 checks establish homogeneous conditions and 37 completed tasks per condition, so this does not affect the archived measurement.

Executor decision: preserve the measured implementation during this closeout. Require condition/header validation before this script is reused for a new measurement. This is a substantive future-reuse limitation, not a cosmetic issue. Cost of deferral: a future operator must not reuse an output folder across conditions without the guard or an equivalent verification.

## Minor findings left unchanged

`git diff --check` over the historical integration range identifies an extra EOF blank line in `plans/2026-10-02-gold-biorxiv.md:1692` and `tests/test_build_biorxiv_script.py:132`. They have no functional impact and historical whitespace cleanup is outside this closeout.

Other saved limitations (zero-input analysis, retry exhaustion, duplicate reporting, rounded means) do not change the current recorded verdicts. Duplicate and consistency checks are preserved.

## Review boundaries and executor decisions

- Current live-provider compatibility and Windows signal handling were not evaluated. This closeout is validated with the offline Linux suite; live/other-platform claims are not made.
- Scientific validity of individual biological labels and the next Co-Scientist study design were not evaluated. The report preserves the existing labels and marks the next research choices open.
- Post-merge and new-worktree verification were pending at review time. The executor must complete both before declaring integration finished.
