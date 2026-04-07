# Evolution-Reasoning: SKILL.md / Mermaid Reconciliation Plan

**Date:** 2026-04-06
**Scope:** 9 issues (4 MAJOR, 5 MINOR) across 2 files
**Estimated Complexity:** MEDIUM
**Files:**
- `packages/skills/evolution-reasoning/SKILL.md` (authoritative protocol)
- `docs/reasonforge-evolution-workflow.mermaid` (visual representation)

---

## RALPLAN-DR Summary

### Principles (5)

1. **Single Source of Truth** -- SKILL.md is the authoritative protocol spec. The Mermaid diagram is a faithful visual representation. When they disagree, we resolve toward the better design, then update BOTH to match.
2. **Practical Placement** -- Protocol steps should appear where they are most actionable. Stagnation checks belong where they can short-circuit unnecessary work (Phase 3, before selection), not in a retrospective termination phase.
3. **Defensive Completeness** -- Every state, transition, and termination path defined in one artifact must exist in the other. No silent omissions.
4. **Conservative Defaults** -- Default values must be consistent everywhere they appear. A single canonical default per parameter.
5. **Minimal Disruption** -- Changes should be surgical. Do not restructure sections or flows that are already consistent.

### Decision Drivers (top 3)

1. **Consistency over cleverness** -- Resolving each discrepancy matters more than which "side" wins. Both artifacts must say the same thing.
2. **Reviewer consensus** -- Where 3 review agents agreed on the better design (e.g., stagnation in Phase 3, benchmark in threshold check), adopt that recommendation.
3. **Executor clarity** -- An LLM agent following SKILL.md must produce behavior that matches the Mermaid diagram step-for-step. Ambiguity is a bug.

### Viable Options

#### Option A: SKILL.md-primary reconciliation (CHOSEN)
Update SKILL.md to adopt better designs from Mermaid where reviewers agreed, then update Mermaid to match SKILL.md for everything else.

| Pros | Cons |
|------|------|
| SKILL.md remains the canonical spec | Requires careful sequencing to avoid circular changes |
| Adopts practical improvements from Mermaid (stagnation, benchmark) | Some SKILL.md sections need structural edits |
| Matches reviewer consensus on all 9 issues | -- |

#### Option B: Mermaid-primary reconciliation (INVALIDATED)
Treat Mermaid as the source of truth and rewrite SKILL.md to match.

| Pros | Cons |
|------|------|
| Mermaid is already more precise on some flows | Mermaid lacks Step 1.1 classification entirely -- a mandatory protocol step |
| -- | Mermaid has no `failed` state -- less complete state machine |
| -- | SKILL.md contains prose guidance (personas, calibration, error recovery) that cannot be represented in a diagram |

**Invalidation rationale:** Mermaid is a visualization tool, not a spec format. It omits critical protocol details (classification, failed state, prose guidance). Making it the primary source would lose information. The correct flow is: fix the spec, then make the diagram match.

---

## Task Flow

### Step 1: Add Classification Node to Mermaid (MAJOR #1)

**Problem:** SKILL.md defines a mandatory Step 1.1 classification with `=== CLASSIFICATION ===` output block. Mermaid skips directly from entry decision to "Generate N Diverse Candidates."

**Changes to `docs/reasonforge-evolution-workflow.mermaid`:**

- Add a new `classify` node between `entry_decision -->|"Full Cycle"| populate` and the current `populate` node.
- New node text: `"Phase 1a: Classify Question\n(select category + dimensions;\nemit === CLASSIFICATION === block)"`
- Style it as `:::agent` (it is an LLM reasoning step).
- Wire: `entry_decision -->|"Full Cycle"| classify --> populate`
- For Refinement Only mode, classification still happens (per Quick Reference line 407: "still output classification block"). Wire: `entry_decision -->|"Refinement Only"| classify_refine` where `classify_refine` is a variant node labeled `"Classify (Refinement)\n(use provided dimensions;\nemit === CLASSIFICATION === block)"` that flows into `items_provided`.
- Alternatively (simpler): insert `classify` before the `state_block_1` node so both paths flow through it: `populate --> classify --> state_block_1` and `items_provided --> classify --> state_block_1`. This matches the "still output classification block" instruction.

**Changes to `packages/skills/evolution-reasoning/SKILL.md`:** None needed -- SKILL.md already has this step correctly defined.

**Acceptance Criteria:**
- [ ] Mermaid diagram contains a classification node
- [ ] Both Full Cycle and Refinement Only paths pass through classification before scoring
- [ ] Node text references the `=== CLASSIFICATION ===` output block
- [ ] Diagram renders without syntax errors

---

### Step 2: Reconcile Budget Check (MAJOR #2)

**Problem:** Mermaid has an active `budget_check` decision node with a `completed_budget` terminal. SKILL.md only mentions budget as an informational note (line 52), not as a termination condition.

**Design Decision:** Promote the budget check from informational to a real termination condition. Reviewers agreed the Mermaid design is better -- unbounded evaluation is a practical risk (token cost, context window). The budget note already exists at line 52; it just needs to become an enforceable rule.

**Changes to `packages/skills/evolution-reasoning/SKILL.md`:**

- In the Configuration section (around line 52), change the evaluation budget note from informational to normative:
  - Current: `> **Evaluation budget**: Total evaluations are bounded by...`
  - New: Add a row to the Configuration table: `| budget_limit | int | NO | population_limit x generation_limit | Maximum total candidate evaluations. When exhausted, terminate with best available. |`
  - Update the note to reference the config parameter and state it is an enforceable termination condition.
- In the State Machine section (around line 74-96):
  - Add `budget_exhausted` as a transition from `scoring` to `completed`.
  - Or more simply: add a note that `scoring` can transition to `completed` when budget is exhausted.
- In Phase 5 Termination (around line 322-333), add budget exhaustion as termination condition #4:
  - `4. **Budget exhausted**: Total evaluations have reached budget_limit. Return the best available.`
- In the termination reason enum (line 341), add `budget_exhausted`.

**Changes to `docs/reasonforge-evolution-workflow.mermaid`:** None needed -- Mermaid already has this correctly.

**Acceptance Criteria:**
- [ ] SKILL.md Configuration table includes `budget_limit` parameter
- [ ] SKILL.md state machine mentions budget exhaustion as a `scoring -> completed` transition
- [ ] Phase 5 lists budget exhaustion as a termination condition
- [ ] Termination reason enum includes `budget_exhausted`
- [ ] Budget note updated from informational to normative

---

### Step 3: Move Stagnation Check to Phase 3 in SKILL.md (MAJOR #3)

**Problem:** SKILL.md puts stagnation detection in Phase 5 (Termination). Mermaid puts it in Phase 3 (after gen-limit check, before selection). Reviewers unanimously agreed Mermaid's placement is more practical -- stagnation should be checked BEFORE wasting effort on selection/mutation.

**Changes to `packages/skills/evolution-reasoning/SKILL.md`:**

- Remove the stagnation block from Phase 5 (lines 327-333). Keep stagnation as a listed termination reason in the bullet list but remove the detection logic from Phase 5.
- Add a new Step 3.1.5 (between current 3.1 gen-limit check and 3.2 rank-and-select) in Phase 3:
  ```
  **Step 3.1b: Check for stagnation**

  If generation >= 2 and best fitness has not improved by more than 0.02 for 2 consecutive generations:
  - Report the plateau: "Best fitness has been ~X.XX for N generations"
  - Try ONE recovery strategy:
    a) Generate a completely new candidate from scratch (fresh seed)
    b) Apply a radical mutation (change the fundamental approach, not details)
  - If the fresh approach does not improve after scoring, status becomes `completed` (stagnation). Go to Phase 5.
  - If it improves, continue with selection (Step 3.2).
  ```
- Update Phase 5 to reference stagnation as a reason but not contain the detection logic. Keep the termination reason `stagnation` in the enum.

**Changes to `docs/reasonforge-evolution-workflow.mermaid`:** None needed -- Mermaid already has this correctly placed.

**Acceptance Criteria:**
- [ ] Stagnation detection logic appears in Phase 3, between gen-limit check and selection
- [ ] Phase 5 still lists `stagnation` as a termination reason but no longer contains detection logic
- [ ] Recovery strategy (fresh seed or radical mutation) is described in Phase 3
- [ ] Quick Reference section updated to reflect Phase 3 stagnation check

---

### Step 4: Add `failed` State to Mermaid (MAJOR #4)

**Problem:** SKILL.md state machine table defines `failed` ("Generation limit reached with no scored candidates"). No corresponding node exists in the Mermaid diagram.

**Changes to `docs/reasonforge-evolution-workflow.mermaid`:**

- Add a `failed` terminal node: `failed["FAILED\n(generation limit reached\nwith no scored candidates)"]:::terminal`
- Add an edge from `gen_limit_check` (or from an appropriate decision point) to `failed`. The condition is: generation limit reached AND no candidates have been scored.
- Practically, this is an edge case (if scoring fails entirely for all generations). The most logical placement is a guard on `completed_genlimit`: if generation limit is reached and population has zero scored candidates, go to `failed` instead of `completed_genlimit`.
- Alternatively, add a decision node after `gen_limit_check -->|"Yes"` that checks "Any scored candidates?" and routes to `failed` vs `completed_genlimit`.

**Changes to `packages/skills/evolution-reasoning/SKILL.md`:** None needed -- already defined correctly.

**Acceptance Criteria:**
- [ ] Mermaid diagram contains a `failed` terminal node
- [ ] An edge path leads to `failed` with the correct condition (gen limit + no scored candidates)
- [ ] `failed` node is styled as `:::terminal`
- [ ] Diagram renders without syntax errors

---

### Step 5: Fix `population_limit` Default Inconsistency (MINOR #5)

**Problem:** Three different defaults appear in SKILL.md:
- Config table (line 43): default = 5
- Step 1.2 (line 159): "default 3"
- Quality Standards (line 381): "population_limit = 3"

**Design Decision:** Use `3` as the canonical default. The Quality Standards section explicitly justifies this ("balances quality improvement against token cost"), and the evaluation budget note at line 52 would need updating. The config table's `5` appears to be a legacy value from before the recommended-defaults guidance was added.

**Changes to `packages/skills/evolution-reasoning/SKILL.md`:**

- Config table (line 43): Change default from `5` to `3`.
- Evaluation budget note (line 52): Update `(5x5=25)` to `(3x5=15)` (or `3x3=9` if generation_limit default is also 3). Check: config table says `generation_limit` default is 5, Quality Standards says 3. Align both to 3.
  - Config table `generation_limit` (line 44): Change default from `5` to `3`.
  - Budget note: Update to `(3x3=9)`. Update maximum to remain `10x10=100`.
- Verify Step 1.2 (line 159) already says "default 3" -- no change needed there.
- Verify Quality Standards (line 381) already says 3 -- no change needed there.

**Changes to `docs/reasonforge-evolution-workflow.mermaid`:** None needed -- Mermaid does not reference specific default values.

**Acceptance Criteria:**
- [ ] Config table shows `population_limit` default = 3
- [ ] Config table shows `generation_limit` default = 3
- [ ] Evaluation budget note uses 3x3=9 as the recommended default calculation
- [ ] Maximum budget remains 10x10=100
- [ ] No other location in SKILL.md contradicts the default of 3

---

### Step 6: Add Benchmark Condition to SKILL.md Threshold Check (MINOR #6)

**Problem:** SKILL.md Phase 2 transition (line 231) says "If best fitness >= threshold" without mentioning benchmark. Mermaid correctly says "fitness >= threshold AND benchmark passed (if applicable)."

**Changes to `packages/skills/evolution-reasoning/SKILL.md`:**

- Phase 2 post-scoring transition (around line 231): Change from:
  - `If best fitness >= threshold: Status becomes completed`
  to:
  - `If best fitness >= threshold (AND benchmark passed, if benchmark is configured): Status becomes completed`
- State Machine table (line 90): Update `scoring` row's "Transitions To" to mention benchmark:
  - `completed (if threshold met AND benchmark passed, when configured) or ready_to_select`
- Quick Reference Phase 2 (line 415): Update the transition line to include benchmark condition.

**Changes to `docs/reasonforge-evolution-workflow.mermaid`:** None needed -- already correct.

**Acceptance Criteria:**
- [ ] Phase 2 threshold check explicitly mentions benchmark gate
- [ ] State machine table `scoring` row includes benchmark in transition condition
- [ ] Quick Reference Phase 2 includes benchmark condition
- [ ] Wording matches Mermaid: "AND benchmark passed (if applicable)"

---

## Risk Considerations

1. **Step 3 (stagnation relocation) is the highest-risk change** -- moving logic between phases could introduce inconsistencies in the Quick Reference, state machine diagram, or integration examples. The executor must search for ALL references to stagnation in SKILL.md and update them.

2. **Step 5 (default changes) has downstream implications** -- if any other files in the repo reference the old defaults (5), they will become inconsistent. The executor should grep the entire repo for `population_limit.*5` and `generation_limit.*5` patterns.

3. **Step 2 (budget promotion) adds a new config parameter** -- this is a protocol change, not just a consistency fix. Any MCP tool mapping or CLI integration that does not support `budget_limit` will need a note that it is derived from `population_limit x generation_limit` by default.

4. **Step 1 (classification in Mermaid) requires careful wiring** -- the Refinement Only path's classification behavior is subtle ("still output classification block" but "skip this phase"). The executor must test that the diagram does not imply Refinement Only skips classification.

---

## Order of Operations

Execute in this order to minimize rework:

1. **Step 5** (defaults) -- smallest, most mechanical change. Establishes consistent baseline values.
2. **Step 6** (benchmark in threshold) -- small textual additions, no structural changes.
3. **Step 2** (budget promotion) -- adds new content to SKILL.md, does not move existing content.
4. **Step 3** (stagnation relocation) -- structural edit within SKILL.md, highest risk, do after simpler changes.
5. **Step 4** (failed state in Mermaid) -- Mermaid-only addition, independent of SKILL.md changes.
6. **Step 1** (classification in Mermaid) -- Mermaid structural change, do last as it requires the most careful wiring.

After all 6 steps, address the remaining 3 MINOR issues inline:

7. **Issue #7** (Refinement Only + Step 1.1 ambiguity): Resolved by Step 1's classification wiring. Additionally, update SKILL.md Phase 1 prose (line 123: "Skip this phase if items are provided") to say: "Skip candidate generation if items are provided, but STILL output the classification block with `Category: refinement` and the provided dimensions."
8. **Issue #8** (All Scored? loop model): Add a note to SKILL.md Phase 2 clarifying that candidates may be scored in batch or sequentially -- the diagram's per-candidate loop is a visual representation of the same logical operation.
9. **Issue #9** (survivor_count >= population_limit guard): Add a validation rule to SKILL.md Configuration section: "Constraint: `survivor_count` must be strictly less than `population_limit`. If `survivor_count >= population_limit`, no candidates are eliminated and evolution cannot progress."

---

## Success Criteria

- [ ] All 9 issues resolved with changes to both files
- [ ] SKILL.md and Mermaid diagram describe the same protocol with zero contradictions
- [ ] Mermaid diagram renders without syntax errors (validate with mermaid-cli or equivalent)
- [ ] Every state in SKILL.md's state machine table has a corresponding node in Mermaid
- [ ] Every decision node in Mermaid has a corresponding check described in SKILL.md
- [ ] Default values are consistent across all locations in SKILL.md (config table, inline references, Quality Standards, Quick Reference)
- [ ] Quick Reference section reflects all structural changes (stagnation placement, benchmark condition, budget termination)
