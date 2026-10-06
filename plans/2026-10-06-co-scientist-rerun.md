# Co-Scientist bounded rerun plan

User authorized loosening execution conditions and retesting, and asked whether Opus stopped due to biomedical subject matter. Inline execution in the existing isolated co-scientist-pilot worktree; preserve prior records and main.

## Approved intent and selected implementation

User explicitly approved retaining ALS/AML and excluding Opus after [bio] refusal. Keep the same ALS/AML evidence, three user-selected panel models: GPT, Grok and GLM Flash, three evolution rounds, 30 nominal backend calls per generation run, held-out DeepSeek evaluation, and blinded expert material. Make 400–800 words a warning rather than a whole-run stop. Increase each run to 45 minutes/800,000 reported tokens; request timeout 600 seconds. Keep the four-hour global clock and reserve up to 40 minutes for independent evaluation. A returned unusable structure gets at most one format retry; backend errors, timeouts and explicit refusals never do. Each run has an absolute 40-call cap. Fresh allowance is 328 including diagnostics; recovery after the interrupted 22-call attempt is 346, below the original absolute 404-call ceiling.

Run the two multi-model cases first, sequentially. Then run three independent provider chains concurrently; each chain runs ALS then AML, sharing no backend with another active chain. Maximum generation scheduling duration is 180 minutes under the 45-minute run cap, within the 200-minute generation allowance. Global deadline overrides every local cap. No safety-refusal bypass, silent model substitution or controller retries. Diagnostics use neutral and unchanged original ALS inputs; never change wording to evade a refusal.

## Task 1: Diagnose Opus and record cause limits

Compare neutral/simple-schema, neutral/original-schema and unchanged ALS/original-schema requests. Record safe failure categories/public outputs and numeric usage; no raw private reasoning or credentials. Confirm whether the unchanged biomedical request is currently supported before launching full runs. Do not infer an old cause from absent stderr.

Keep the initial population at four for both methods. Rotate the duplicated multi-model seed author across cases. Two non-author critics per multi-model candidate and two fresh self-critics per solo candidate produce ten authored candidates and twenty critiques per run. Eight method/case runs plus four evaluations and four diagnostic attempts. Opus is excluded from all generation and scoring.

## Task 2: Relaxed profile and controlled scheduling

TDD: original strict behavior remains reproducible; relaxed writing retains 812/917-word valid hypotheses with warnings. Malformed/empty returned structure gets one additional attempt, then stops. Profile fingerprints and budget limits are recorded. Fake full study completes 240 nominal generation calls plus four held-out calls, consumes diagnostic usage without double counting, runs independent provider chains concurrently while maintaining one active run per backend, and stops/cancels at global limits. Implement a separate relaxed protocol/profile, not edits to old frozen inputs/default main.

Recovery after the first relaxed attempt: preserve the interrupted output unchanged and carry all 22 admitted calls, 153,786 reported tokens, nine unknown-usage calls and the original diagnostic clock into a fresh directory exactly once. Use the existing native Codex 0.160.0 binary through this worker's PATH because the global npm symlink is broken; no global installation or model change. Independent formatting and accounting fixes use the dispatching-parallel-agents skill with disjoint file ownership and offline tests.

## Task 3: Verification and bounded live rerun

Run targeted and full offline tests; dry-run; one fresh read-only independent reviewer before live execution. Fix material findings with regression tests. Freeze source/config/protocol and diagnostic accounting. Start a fresh output folder under the original diagnostic clock; do not overwrite past results. Verify actual completed/failed/unstarted slots, public traces, source hashes, full final comparisons, independent evaluations and expert packet. Report incomplete comparisons explicitly and keep the branch/worktree locally.

## Task 4: Post-launch parser repair for the next execution

The immutable live0.3 GLM/AML run returned four substantive public critique points; the inherited maximum-three parser rejected them, then the one format retry failed inside backend structured parsing. Record both failures, not a scientific quality verdict. Add a default-preserving judge-parser hook; under relaxed0.4 validate all scores and retain every nonempty public point when the preferred1–3 count is exceeded. Log an advisory anomaly. TDD proves four-point solo runs finish all30 calls with no retry, while strict profiles and malformed scores/empty points still fail. This is an offline repair only: the active study keeps its frozen0.3 inputs and original code commit; do not launch more generation slots or retroactively change its failed status.
