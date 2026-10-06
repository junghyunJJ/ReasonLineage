## Task 2: Case data, protocol and controlled runner

Files: `research/co-scientist-pilot/protocol/`, `src/reasonlineage/pilot/run.py`, `tests/test_pilot_run.py`.
Consumes: metered backends and budgets from Task 1; existing Runner, EventLog, CallRecorder, corpus and config.
Produces: method/case header, 40-call complete traces, initial best and final best, budget/failure status with no live evaluation feedback.

- [ ] Test actual fake-backed multi-model and solo runs: 10 candidates, 30 recorded critics, 40 calls; solo has no crossovers and fresh critic names.
- [ ] Test strict output rejection without realignment/retry, input/config fingerprint isolation, public records and partial failure.
- [ ] Observe failures, implement pilot-only overrides and a separate protocol, verify targeted tests and full suite.
- [ ] Commit and ledger.
