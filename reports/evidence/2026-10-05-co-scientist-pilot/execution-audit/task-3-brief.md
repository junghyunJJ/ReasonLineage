## Task 3: Study, anonymous export and independent review

Files: `src/reasonlineage/pilot/review.py`, `src/reasonlineage/pilot/study.py`, `scripts/run_co_scientist_pilot.py`, `tests/test_pilot_review.py`, `tests/test_pilot_study.py`.
Consumes: Task 2's status/results; Task 1's global metering; pinned corpus/config.
Produces: dry-run plan; ten isolated generation slots; anonymous proposals, pairs and analyst-only mapping; four reversed-order held-out reviews; separate citation audit; summary and expert packet.

- [ ] Test anonymous identity isolation, duplicate reuse, initial/final pairing, response ID validation and bibliography checks.
- [ ] Test dry-run without backend calls, refuse output reuse, bounded partial scheduling and total call accounting using real runners with fake services.
- [ ] Implement after failing tests; run full offline suite and CLI dry-run.
- [ ] Commit; obtain one read-only independent review; fix material findings with regression tests.
