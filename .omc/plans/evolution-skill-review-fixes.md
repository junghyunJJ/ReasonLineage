# Evolution-Reasoning Skill Review Fixes

**Created:** 2026-04-04
**Status:** DRAFT — Awaiting consensus review
**Scope:** 17 issues across `packages/core/src/`, `packages/mcp/src/`, `packages/skills/evolution-reasoning/`

---

## RALPLAN-DR Summary

### Principles

1. **Domain-agnostic by default** — The type system and fitness calculation must work with arbitrary dimensions, not just the three hardcoded ones. The three defaults exist only as a convenience fallback.
2. **State machine fidelity** — The MCP server's status transitions must exactly match the state diagram in SKILL.md. A single mutation must not prematurely close the mutation window.
3. **Defensive validation** — Score dimensions submitted by agents must be validated against session weights. Silent mismatches producing fitness=0 are unacceptable.
4. **Backward compatibility** — The core engine is consumed independently. Changes to `types.ts` must not break existing callers that use the three default dimensions.
5. **Documentation-code parity** — SKILL.md parameter names, schemas, and state diagrams must match the actual implementation exactly.

### Decision Drivers (Top 3)

1. **Correctness of the multi-mutation workflow (Issue #1)** — This is the single most impactful bug. It makes the entire Phase 4 workflow described in SKILL.md impossible to execute. Fixing this unblocks the core evolutionary loop.
2. **Type system flexibility (Issue #3)** — The hardcoded `logicalConsistency`/`evidenceGrounding`/`solutionUsefulness` fields in `JudgeWeights`, `CandidateJudgeResult`, `ScoredCandidate`, and `EvolutionEvent` contradict the "domain-agnostic" claim and create maintenance burden for every new dimension set.
3. **Score validation (Issue #2)** — Without validation, agents can submit scores on dimensions that don't match session weights, producing silent fitness=0 results that poison the evolutionary process.

### Viable Options

#### Option A: Minimal Targeted Fixes (Recommended)

Fix the 3 critical issues and the 6 high-severity issues with focused, surgical changes. Defer medium-severity improvements to a follow-up. Keep the three default dimensions as optional convenience fields with deprecation path.

| Pros | Cons |
|------|------|
| Smallest blast radius; low risk of regressions | Medium issues remain unfixed |
| Can be completed and tested in a single PR | Type deprecation requires a follow-up migration |
| Backward compatible with existing core engine callers | |
| All critical and high issues resolved | |

#### Option B: Full Refactor — Pure Dynamic Dimensions

Remove all hardcoded dimension fields from types, making everything purely `Record<string, number>`. Fix all 17 issues including medium-severity ones in one pass.

| Pros | Cons |
|------|------|
| Clean, future-proof type system | Breaking change for core engine callers |
| All 17 issues resolved at once | Larger PR, harder to review and test |
| No deprecated fields to clean up later | Higher risk of regressions in engine.ts |
| | Requires updating EvolutionEvent type (breaks event consumers) |

#### Option C: Shim Layer — Keep Old Types, Add New Dynamic API

Add a new parallel set of types (`DynamicScoredCandidate`, etc.) alongside the old ones. MCP server uses the new types; core engine keeps old types for backward compat.

| Pros | Cons |
|------|------|
| Zero breaking changes | Two parallel type hierarchies to maintain |
| Core engine completely untouched | Confusing API surface |
| | More code to write and test |
| | Defers the real cleanup indefinitely |

### Recommended Option: **A — Minimal Targeted Fixes**

**Why:** The critical and high issues are where real user-facing bugs live. The medium issues are quality-of-life improvements that can wait. Option A fixes what matters without risking the stable core engine API. The type system changes in Option A use a backward-compatible approach: keep the three fields as optional (not required), add a clean `scores: Record<string, number>` as the primary field, and make `calculateFitness` use `scores` exclusively when present.

---

## Context

The evolution-reasoning skill was reviewed by three independent agents who found 17 issues ranging from critical state-machine bugs to documentation mismatches. The issues span three packages: `@reasonforge/core` (types, scoring), `@reasonforge/mcp` (server tools, session, schemas), and the SKILL.md protocol document.

## Work Objectives

1. Fix the 3 critical bugs that break the evolutionary loop
2. Fix the 6 high-severity issues that cause inconsistencies and confusion
3. Add test coverage for every critical and high fix
4. Align SKILL.md and scoring_guide.md with the corrected implementation

## Guardrails

### Must Have
- All existing tests continue to pass after changes
- New tests for each critical/high fix
- Backward compatibility for `@reasonforge/core` public API
- SKILL.md state diagram matches actual transitions
- `pnpm test` passes in both `packages/core` and `packages/mcp`

### Known Acceptable Breaking Changes
- Making required fields optional on `JudgeWeights`, `CandidateJudgeResult`, and `ScoredCandidate` is a TypeScript source-breaking change (callers accessing without optional chaining get compiler errors). This is acceptable at v0.1.0 with no external consumers. The only internal consumer (`engine.ts`) will be updated in the same PR.
- `calculateFitness` signature changes from 3-arg to 2-arg (direct migration, no overload). Both call sites updated atomically.

### Must NOT Have
- Breaking changes to `RunReasonForgeCycleInput` or its callback signatures
- New dependencies added
- Changes to `packages/core/src/engine.ts` control flow (only type adjustments)
- Removal of any existing exported type (deprecate instead)

---

## Task Flow

```
Phase 1 (Core Types + Scoring)
    |
    v
Phase 2 (MCP State Machine + Validation)
    |
    v
Phase 3 (Documentation Alignment)
    |
    v
Phase 4 (Test Coverage)
```

Phase 1 must complete before Phase 2 (MCP imports core types).
Phase 2 must complete before Phase 3 (docs describe the corrected behavior).
Phase 4 can partially overlap with Phases 2-3 (test-as-you-go).

---

## Phase 1: Core Type System + Scoring Fix

**Issues addressed:** #3 (CRITICAL), #11 (MEDIUM — included because it is one line and blocks score validation)

**Files to modify:**
- `packages/core/src/types.ts`
- `packages/core/src/scoring.ts`
- `packages/core/src/engine.ts` (minimal — only the `scoreCandidate` helper's return type construction)

### TODO 1.1: Make `JudgeWeights` and `CandidateJudgeResult` fully dynamic

**Current state:** Both types require `logicalConsistency`, `evidenceGrounding`, `solutionUsefulness` as mandatory fields plus an index signature. This forces callers with custom dimensions to satisfy three irrelevant fields.

**Change:** Make the three fields optional (not removed — backward compat). The canonical shape becomes `Record<string, number>` with the three defaults as optional convenience.

```typescript
// types.ts — BEFORE
export type JudgeWeights = {
  logicalConsistency: number;
  evidenceGrounding: number;
  solutionUsefulness: number;
  [dimension: string]: number;
};

// types.ts — AFTER
export type JudgeWeights = {
  logicalConsistency?: number;
  evidenceGrounding?: number;
  solutionUsefulness?: number;
  [dimension: string]: number | undefined;
};
```

Apply the same pattern to `CandidateJudgeResult`.

**Acceptance criteria:**
- `JudgeWeights` accepts `{ accuracy: 0.4, clarity: 0.6 }` without requiring the three default fields
- `defaultJudgeWeights` in `scoring.ts` still type-checks (it provides all three)
- Existing code in `engine.ts` that reads `scores.logicalConsistency` still compiles (optional access)

### TODO 1.2: Make `ScoredCandidate` use `scores` as primary, defaults as optional

**Current state:** `ScoredCandidate` has three mandatory fields (`logicalConsistency`, `evidenceGrounding`, `solutionUsefulness`) plus an optional `scores?: Record<string, number>`. This is inverted.

**Change:**
```typescript
// types.ts — AFTER
export type ScoredCandidate = Candidate & {
  fitness: number;
  critique: string[];
  benchmarkVerdict: BenchmarkVerdict;
  scores: Record<string, number>;  // PRIMARY — always present
  /** @deprecated Use scores['logicalConsistency'] instead */
  logicalConsistency?: number;
  /** @deprecated Use scores['evidenceGrounding'] instead */
  evidenceGrounding?: number;
  /** @deprecated Use scores['solutionUsefulness'] instead */
  solutionUsefulness?: number;
};
```

**Acceptance criteria:**
- `scores` is required (not optional) on `ScoredCandidate`
- The three legacy fields are optional with `@deprecated` JSDoc
- `engine.ts:scoreCandidate` still populates the three legacy fields for backward compat (reading from `scores`)

### TODO 1.3: Simplify `calculateFitness` — direct migration, no overload

**Current state:** `scoring.ts` has two paths — one for hardcoded fields, one for `dynamicScores`. The hardcoded path is dead code when dynamic scores are provided.

**Change:** Replace with a single new signature (NO overload — overloads are dangerous here because `CandidateJudgeResult` is structurally assignable to `JudgeWeights`, causing TypeScript to silently route 3-arg calls to the wrong 2-arg overload):

```typescript
export function calculateFitness(
  weights: JudgeWeights,
  scores: Record<string, number>
): number {
  let total = 0;
  for (const key of Object.keys(weights)) {
    const w = weights[key];
    if (w != null) {
      total += (scores[key] ?? 0) * w;
    }
  }
  return total;
}
```

**Migrate both call sites atomically:**

1. `engine.ts:63` — BEFORE: `calculateFitness(scores, input.strategy?.weights, scores as Record<string, number>)` → AFTER: `calculateFitness(input.strategy?.weights ?? defaultJudgeWeights, { ...scores } as Record<string, number>)`
2. `tools.ts:143-144` — BEFORE: `const defaultShell = ...; calculateFitness(defaultShell, session.config.weights, input.scores)` → AFTER: Remove `defaultShell` entirely. Use `calculateFitness(session.config.weights, input.scores)`

**Why no overload:** At v0.1.0 with only 2 internal call sites, a clean signature break is safer than an overload that risks silent misrouting. Both call sites are updated in the same commit.

**Acceptance criteria:**
- `calculateFitness({ accuracy: 0.4, clarity: 0.6 }, { accuracy: 0.9, clarity: 0.7 })` returns `0.78`
- Both call sites (`engine.ts:63`, `tools.ts:144`) updated to new signature
- `defaultShell` variable removed from `tools.ts`
- Existing scoring tests updated to new signature and pass

### TODO 1.4: Add weight normalization validation

**Current state:** `scoring_guide.md` says "Weights must sum to ~1.0. If they don't, normalize before calculating." No code enforces this.

**Change:** Add a `normalizeWeights` utility in `scoring.ts`. `calculateFitness` calls it internally. Warn (do not throw) if sum deviates from 1.0 by more than 0.05.

**Acceptance criteria:**
- `calculateFitness({ a: 2, b: 3 }, { a: 1, b: 1 })` produces the same result as if weights were `{ a: 0.4, b: 0.6 }`
- No runtime error for non-normalized weights (just normalization)

### TODO 1.5: Update `EvolutionEvent` type for dynamic dimensions

**Current state:** The `candidate.scored` event variant has hardcoded `logicalConsistency`, `evidenceGrounding`, `solutionUsefulness` fields.

**Change:** Make those three optional, add `scores: Record<string, number>` as required. Update `engine.ts:scoreCandidate` to populate `scores` and optionally populate the three legacy fields.

**Acceptance criteria:**
- Event type accepts custom dimension scores without the three defaults
- Existing event consumers that read the three fields still compile (optional access)

---

## Phase 2: MCP Server State Machine + Validation Fixes

**Issues addressed:** #1 (CRITICAL), #2 (CRITICAL), #4 (HIGH), #5 (HIGH), #7 (HIGH), #9 (HIGH), #12 (MEDIUM — included because it is a one-line fix with high impact), #17 (MEDIUM — included because it is a one-line fix)

**Files to modify:**
- `packages/mcp/src/tools.ts`
- `packages/mcp/src/session.ts`
- `packages/mcp/src/schemas.ts`

### TODO 2.1: Fix premature `mutating -> scoring` transition (Issue #1 — CRITICAL)

**Current state:** Both `handleMutate` (line 257) and `handleCrossover` (line 302) immediately set `status: "scoring"` when registering a new candidate. This means after the first mutation, the session transitions to `scoring` and rejects further mutations or crossovers because `handleMutate` requires `status === "mutating"`.

**Root cause:** The status transition happens at registration time instead of when the agent explicitly signals "I'm done mutating."

**Change:** 
1. Do NOT change status in `handleMutate` or `handleCrossover`. Keep status as `mutating` while registering genetic operations.
2. Add a new tool `handleFinalizeMutations` (or repurpose the existing `next_step` logic) that transitions `mutating -> scoring` when the agent is done submitting mutations/crossovers.
3. **Simpler alternative (recommended):** Allow `handleScoreCandidate` to accept candidates when status is `mutating` OR `scoring`. The first call to `handleScoreCandidate` on a pending candidate implicitly transitions to `scoring`. This avoids adding a new tool.

**Recommended approach — keep `mutating` status while adding candidates:**
- `handleMutate` and `handleCrossover`: Add candidate to `pendingCandidates` but do NOT change status. Stay in `mutating`.
- `handleScoreCandidate`: Accept scoring when status is `mutating` (auto-transition to `scoring`) OR when already `scoring`.
- **CRITICAL TIMING:** The `mutating → scoring` transition must happen at the **beginning** of `handleScoreCandidate`, BEFORE processing the score. Specifically: if `session.status === "mutating"`, set `status: "scoring"` immediately. This prevents interleaving (score one → mutate another → score rest).
- This allows: mutate -> mutate -> crossover -> score -> score -> score (the multi-operation workflow SKILL.md describes).

**Also update `handleNextStep` `mutating` branch (tools.ts:371-381):**
- Current: always suggests `reasonforge_mutate` when status is `mutating`.
- After fix: check `session.pendingCandidates.length > 0`. If pending candidates exist, suggest BOTH options: "You can submit more mutations/crossovers, or start scoring the N pending candidate(s)." If no pending candidates, suggest mutation only.

**Acceptance criteria:**
- Can call `handleMutate` twice in a row without error
- Can call `handleMutate` then `handleCrossover` without error
- Calling `handleScoreCandidate` while in `mutating` status auto-transitions to `scoring` BEFORE processing
- Once in `scoring`, further mutations/crossovers are rejected (pending candidates must be scored first)
- `handleNextStep` in `mutating` with pending candidates suggests scoring option
- The existing test "runs a complete evolution cycle" still passes

### TODO 2.2: Validate score dimensions match session weights (Issue #2 — CRITICAL)

**Current state:** `handleScoreCandidate` accepts any `Record<string, number>` as scores without checking that the keys match the session's configured weight keys. Submitting `{ foo: 0.9 }` when weights are `{ accuracy: 0.5, clarity: 0.5 }` silently produces fitness ~0.

**Change:** In `handleScoreCandidate`, after retrieving the session:
1. Get the set of weight keys from `session.config.weights`.
2. Get the set of submitted score keys from `input.scores`.
3. Compute `missingDimensions` = weight keys not in score keys.
4. Compute `extraDimensions` = score keys not in weight keys.
5. If `missingDimensions` is non-empty, throw an error naming the missing dimensions.
6. If `extraDimensions` is non-empty, log a warning but do not throw (forward compatibility).

**Acceptance criteria:**
- Submitting `{ foo: 0.9 }` when weights are `{ accuracy: 0.5, clarity: 0.5 }` throws an error mentioning "accuracy" and "clarity"
- Submitting `{ accuracy: 0.9, clarity: 0.8, extra: 0.5 }` succeeds (extra dimensions ignored in fitness but not rejected)
- Submitting `{ accuracy: 0.9, clarity: 0.8 }` when weights are `{ accuracy: 0.5, clarity: 0.5 }` succeeds

### TODO 2.3: Unify generation-limit handling (Issue #4 — HIGH)

**Current state:** `handleSelect` (line 192) throws an error when generation limit is reached. `handleNextStep` (line 346-352) gracefully transitions to `completed`. An agent calling `select` after hitting the limit gets an unhelpful error instead of a clean completion.

**Change:** In `handleSelect`, when `session.generation >= session.config.generationLimit`:
- Instead of throwing, transition to `completed` and return a result indicating the session is finalized with the best candidate.
- Match the behavior of `handleNextStep`.

**Acceptance criteria:**
- `handleSelect` at generation limit transitions to `completed` instead of throwing
- Returns the best candidate info in the response
- `handleNextStep` behavior unchanged
- Existing test "rejects exceeding generation limit in select" updated to expect completion instead of error

### TODO 2.4: Wire up the `failed` status (Issue #5 — HIGH)

**Current state:** `SessionState` defines `"failed"` as a valid status, `assertNotTerminal` checks for it, but no code path ever sets it.

**Change:** Set `status: "failed"` in error scenarios:
1. In `handleStartSession`: if session creation fails (already handled by throws, but wrap with try/catch setting failed on the session if it was partially created).
2. More practically: add a `handleFailSession` tool or add failure detection in `handleNextStep` when the population is empty and generation limit is reached (no viable candidates).

**Simpler approach (recommended):** In `handleNextStep`, when `generationLimitReached` and `best` is null (no scored candidates at all), set status to `failed` instead of `completed`.

**Acceptance criteria:**
- A session that reaches generation limit with zero scored population gets `status: "failed"`
- `assertNotTerminal` correctly blocks operations on failed sessions
- `handleNextStep` returns appropriate message for failed sessions

### TODO 2.5: Add `survivor_count` to `startSessionSchema` (Issue #7 — HIGH)

**Current state:** SKILL.md says `survivor_count` is a session-level parameter (line 45), but the actual `startSessionSchema` does not include it. It only exists on `selectSchema` as a per-call override.

**Change:**
1. Add `survivorCount` to `startSessionSchema` (optional, default 2).
2. Store it in `SessionConfig`.
3. In `handleSelect`, use `session.config.survivorCount` as the default, allowing per-call override via `input.survivorCount`.

**Acceptance criteria:**
- `startSessionSchema` accepts `survivorCount` field
- `SessionConfig` stores `survivorCount`
- `handleSelect` uses session-level default, overridable per call
- Omitting `survivorCount` from both start and select defaults to 2

### TODO 2.6: Persist parentId on candidates for lineage tracking (Issue #9 — HIGH)

**Current state:** `index.ts` tool descriptions claim "the server tracks lineage" but `Candidate` type is just `{ id, answer }` — no parent reference stored.

**Change:**
1. Add optional `parentIds?: string[]` to `Candidate` type in `types.ts`.
2. In `handleMutate`, set `parentIds: [input.parentId]` on the new candidate.
3. In `handleCrossover`, set `parentIds: [...input.parentIds]` on the new candidate.
4. Include `parentIds` in `ScoredCandidate` so lineage is visible in results.

**Acceptance criteria:**
- Mutated candidates have `parentIds: ["<parentId>"]`
- Crossover candidates have `parentIds: ["<parent1>", "<parent2>"]`
- Seed candidates have `parentIds: undefined` or `parentIds: []`
- Lineage visible in `handleNextStep` and scoring responses

### TODO 2.7: Make `next_step` non-mutating for terminal states (Issue #12 — MEDIUM)

**Current state:** `handleNextStep` (line 352) calls `updateSession` to set `completed` status on a tool that is conceptually a read/check operation.

**Change:** This mutation is actually necessary (it finalizes the session when generation limit is reached). However, rename the branch comment to clarify it is intentional, and ensure repeated calls are idempotent (calling next_step twice when generation limit is reached should not error).

**Acceptance criteria:**
- Calling `handleNextStep` twice on a generation-limit-reached session returns the same result both times without error
- Already the case with current code (second call hits the terminal branch), but add a test to lock this in

### TODO 2.8: Remove `getSession` side-effect (Issue #17 — MEDIUM)

**Current state:** `getSession` (session.ts:59) mutates `lastAccessedAt` on every read. This is a side effect on a getter.

**Change:** Move `lastAccessedAt` update into `updateSession` only. Add a separate `touchSession(sessionId)` function for explicit access-time updates. Call `touchSession` from tool handlers that need to keep the session alive.

**Acceptance criteria:**
- `getSession` is a pure read with no mutation
- Session GC still works (tool handlers call `touchSession`)
- Existing session tests updated

---

## Phase 3: Documentation Alignment

**Issues addressed:** #6 (HIGH), #8 (HIGH), #13 (MEDIUM)

**Files to modify:**
- `packages/skills/evolution-reasoning/SKILL.md`
- `packages/skills/evolution-reasoning/references/scoring_guide.md`

### TODO 3.1: Fix parameter naming mismatch (Issue #6 — HIGH)

**Current state:** SKILL.md uses `dimensions` (line 41) and snake_case (`population_limit`, `generation_limit`, `survivor_count`). Actual schema uses `weights` and camelCase (`populationLimit`, `generationLimit`, `survivorCount`).

**Change:** Update SKILL.md configuration table to match actual schema names:
- `dimensions` -> `weights`
- `population_limit` -> `populationLimit`
- `generation_limit` -> `generationLimit`
- `survivor_count` -> `survivorCount`

Add a note: "When using the MCP server tools, all parameters use camelCase. The `weights` parameter is a dictionary mapping dimension names to their weights."

**Acceptance criteria:**
- Every parameter name in SKILL.md matches the actual schema field name
- camelCase used consistently
- Configuration table updated with correct names

### TODO 3.2: Complete the state diagram (Issue #8 — HIGH)

**Current state:** SKILL.md state diagram (lines 70-77) is missing the `SCORING -> COMPLETED` direct transition that happens when threshold is met after scoring all candidates.

**Change:** Update the diagram:
```
                     +--[threshold met]---> COMPLETED
                     |                         ^
SCORING ---[all scored]---> READY_TO_SELECT    |
   ^                            |              |
   |                     [gen limit]---->------+
   |                            |
   |                       [select]
   |                            |
   |                            v
   +----[score pending]---- MUTATING
```

Also add the `MUTATING -> SCORING` transition label clarification per Issue #1 fix: "Scoring the first pending candidate auto-transitions from MUTATING to SCORING."

**Acceptance criteria:**
- Diagram shows SCORING -> COMPLETED transition
- Diagram shows READY_TO_SELECT -> COMPLETED transition (generation limit)
- Diagram shows MUTATING -> SCORING transition (via scoring a pending candidate)
- Status table updated with these transitions

### TODO 3.3: Fix Refinement Only mode item shape (Issue #13 — MEDIUM)

**Current state:** SKILL.md describes refinement items as `{id, content, scores, critique}` but the actual MCP schema expects `{id, answer}` (same as regular candidates).

**Change:** Update SKILL.md to clarify that in Refinement Only mode:
- Items are passed as regular candidates via `candidates: [{id, answer}]` in `startSessionSchema`
- The calling context should include scores and critique in the calling instructions, not in the candidate data
- Or: if the caller has pre-scored items, they skip to Phase 2 by scoring them immediately after session creation

**Acceptance criteria:**
- SKILL.md Refinement Only section matches actual `startSessionSchema` format
- Example updated to show correct field names

---

## Phase 4: Test Coverage

**Files to modify:**
- `packages/core/tests/scoring.test.ts`
- `packages/mcp/tests/tools.test.ts`
- `packages/mcp/tests/session.test.ts`

### TODO 4.1: Tests for dynamic dimensions (Phase 1 types)

Add to `scoring.test.ts`:
- Test `calculateFitness` with purely custom dimensions (no default three)
- Test weight normalization (weights summing to 2.0)
- Test missing score key returns 0 contribution

**Acceptance criteria:** All new tests pass, existing tests still pass.

### TODO 4.2: Tests for multi-mutation workflow (Issue #1)

Add to `tools.test.ts`:
- Test: mutate -> mutate -> score -> score (two mutations in a row)
- Test: mutate -> crossover -> score -> score -> score (mutation then crossover)
- Test: scoring while in `mutating` status auto-transitions
- Test: once in `scoring`, further mutations rejected

**Acceptance criteria:** Multi-operation Phase 4 workflow works end-to-end.

### TODO 4.3: Tests for score dimension validation (Issue #2)

Add to `tools.test.ts`:
- Test: submitting scores with wrong dimension names throws descriptive error
- Test: submitting scores with extra dimensions succeeds
- Test: submitting scores with subset of dimensions throws

**Acceptance criteria:** Mismatched dimensions produce clear error messages.

### TODO 4.4: Tests for generation limit graceful handling (Issue #4)

Update existing test "rejects exceeding generation limit in select":
- Change expectation from `toThrow` to expect `completed` status in response
- Add test: `handleNextStep` after select-at-limit returns completed

**Acceptance criteria:** Generation limit produces graceful completion, not errors.

### TODO 4.5: Tests for lineage tracking (Issue #9)

Add to `tools.test.ts`:
- Test: mutated candidate has `parentIds` containing parent ID
- Test: crossover candidate has `parentIds` containing both parent IDs
- Test: seed candidates have no parentIds

**Acceptance criteria:** Lineage is persisted and retrievable.

### TODO 4.6: Tests for `failed` status (Issue #5)

Add to `tools.test.ts`:
- Test: session with generation limit reached and no scored population -> `failed`

**Acceptance criteria:** Failed status is reachable and terminal.

### TODO 4.7: Tests for `getSession` purity (Issue #17)

Add to `session.test.ts`:
- Test: calling `getSession` does not change `lastAccessedAt`
- Test: `touchSession` updates `lastAccessedAt`

**Acceptance criteria:** `getSession` is side-effect-free.

---

## Deferred Items (Medium — Follow-Up PR)

These issues are real but lower priority. They should be tracked for a follow-up:

| # | Issue | Why Deferred |
|---|-------|-------------|
| 10 | Stagnation detection unimplemented | Feature addition, not a bug. Requires design for detection threshold. |
| 14 | Evolution event log missing from MCP | Feature addition. MCP SessionState needs a new field + memory management for event accumulation. |
| 15 | Crossover quality / decomposition | SKILL.md persona change, not a code fix. Low-risk improvement. |
| 16 | Score inflation drift / calibration reminder | SKILL.md persona change. Requires design for when to trigger reminders. |

---

## Success Criteria

1. All 3 CRITICAL issues resolved and tested
2. All 6 HIGH issues resolved and tested
3. `pnpm test` passes in `packages/core` and `packages/mcp`
4. SKILL.md state diagram, parameter names, and mode descriptions match implementation
5. No breaking changes to `@reasonforge/core` public API (deprecated fields, not removed)
6. Multi-mutation workflow (mutate -> mutate -> crossover -> score all) works end-to-end
7. Score dimension validation catches mismatches with clear error messages

---

## ADR: Implementation Approach

**Decision:** Option A — Minimal Targeted Fixes with backward-compatible type evolution.

**Drivers:**
1. The critical bugs (#1, #2, #3) block correct usage of the evolution loop
2. The core engine is used independently and must not break
3. The project has no downstream consumers yet, so deprecated fields are a courtesy for future migration

**Alternatives considered:**
- **Option B (Full Refactor):** Rejected because it changes `EvolutionEvent` and `ScoredCandidate` in breaking ways. The engine's `scoreCandidate` helper constructs these types extensively. Full refactor risk is disproportionate to the benefit for a 0.1.0 project.
- **Option C (Shim Layer):** Rejected because dual type hierarchies create long-term maintenance burden that outweighs the zero-breakage benefit. At v0.1.0, the backward-compat concern is manageable with optional fields.

**Why chosen:** Option A fixes all user-facing bugs with minimal code churn. The backward-compatible type changes (required -> optional, new `scores` field promoted to required) let existing code compile while nudging toward the cleaner dynamic-dimensions pattern.

**Consequences:**
- Three `@deprecated` fields on `ScoredCandidate` and `EvolutionEvent` that must be cleaned up before v1.0
- `calculateFitness` signature changed from 3-arg to 2-arg (direct migration, both call sites updated atomically — no overload needed)
- Making required fields optional is a known TypeScript source-breaking change, acceptable at v0.1.0 with zero external consumers
- SKILL.md will be more accurate but still describes features (stagnation detection) that are unimplemented (noted in doc)

**Follow-ups:**
- Remove deprecated fields before v1.0 release
- Implement stagnation detection (Issue #10)
- Add evolution event log to MCP SessionState (Issue #14)
- Design score calibration reminder mechanism (Issue #16)
