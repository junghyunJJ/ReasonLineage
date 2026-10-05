# Gold experiment closeout and Co-Scientist workspace plan

> **For agentic workers:** Use superpowers:executing-plans for this user-approved closeout, then superpowers:finishing-a-development-branch and superpowers:using-git-worktrees. Execute inline; obtain one independent review before merging.

**Goal:** Preserve the existing experiment record, verify and merge the current implementation into local `main`, and create an isolated `co-scientist-pilot` workspace.

**Architecture:** Keep the existing checkout as the local `main` workspace and the home of raw experiment outputs. Store the closeout report and compact evidence in version control, plus an independently verified local archive of ignored records. Start the next branch from the merged `main`.

**Tech stack:** Git, Python 3.12, pytest, tar/gzip, SHA-256.

**Spec:** The user-approved four-step closeout in the 2026-10-05 conversation; experiment interpretation follows `specs/2026-10-03-gold-weather-level2-design.md` and `specs/2026-10-04-gold-weather-level3-design.md`.

## Global constraints

- Preserve `gb.html`, measured tasks, gold files, protocol 1.0.5, and raw run outputs.
- Run offline tests only; do not call real models or rerun biological experiments.
- Merge locally into `main`; do not push or publish.
- Preserve preregistration history with a normal merge, without squash or history rewriting.
- Remove only the finished `gold-weather-l3` branch after a successful merge. Keep unrelated and archival branches.
- Create `.worktrees/co-scientist-pilot` from the merged `main`; `.worktrees` is already ignored.
- Choosing ALS versus AML, input evidence, evaluation criteria, and any paid run remains future research work.

## Review focus

- Ignored `runs/` and `.superpowers/sdd/` must remain available after the branch transition.
- The closure report must distinguish correctness from internal fitness and avoid generalizing weather findings.
- The report must not claim unfinished bioRxiv or unrun arXiv experiments are complete.
- The full offline suite must pass on the feature branch, merged `main`, and the new worktree.
- Git integration must not modify user files, squash preregistration commits, or publish the repository.

## Task 1: Verify the existing implementation

- [x] Reproduce the CLI/process checks in the unrestricted execution environment: 13 tests pass without a source change.
- [x] Run `python -B -m pytest -q -p no:cacheprovider` and retain the full output: 651 passed, 3 deselected in 20.08s.
- [x] If a code defect is demonstrated, fix only its root cause using a failing regression test; otherwise preserve the implementation. No production change was needed.

## Task 2: Preserve and document the experiment record

- [x] Archive ignored run and SDD records under `.archives/2026-10-05-gold-experiments/`.
- [x] Verify archived files against the originals and record the archive SHA-256 and file inventory: 7,740 entries verified.
- [x] Add `reports/2026-10-05-gold-experiments-closeout.md`, compact machine-readable results, and original progress/analysis notes.
- [x] Commit only the intended report/evidence files and this plan; leave `gb.html` untouched (`697a9ff`).
- [x] Obtain an independent review and address material findings before integration: ready to merge; current measurement/preservation has no blocker. Record the important output-folder condition guard required before future reuse.

## Task 3: Integrate and prepare the next workspace

- [ ] Update local `main` from the fetched `origin/main` using fast-forward only, then merge `gold-weather-l3` normally.
- [ ] Verify the merged tree with the full offline suite.
- [ ] Create `co-scientist-pilot` at `.worktrees/co-scientist-pilot` from merged `main`.
- [ ] Verify the new worktree baseline with the full offline suite.
- [ ] Delete only the merged `gold-weather-l3` branch; preserve the original checkout and local archive.
- [ ] Record final commit IDs, workspace paths, test results, and unresolved research choices.
