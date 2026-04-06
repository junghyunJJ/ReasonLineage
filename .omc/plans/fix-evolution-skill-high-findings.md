# Fix 3 HIGH Findings in Evolution-Reasoning Skill

**Date**: 2026-04-04
**Status**: DRAFT - Awaiting consensus review
**Target**: `packages/skills/evolution-reasoning/SKILL.md` (+ `references/scoring_guide.md`)
**Complexity**: MEDIUM (documentation fixes with one design decision on state persistence)

---

## Context

The `evolution-reasoning` skill was migrated from a CLI/MCP tool-based protocol to a pure Anthropic Skills markdown protocol. An adversarial Codex review found 3 HIGH severity findings where the skill document diverges from the reference implementations in `packages/skill-runner/src/handlers.ts` and `packages/core/src/engine.ts`.

All three findings are specification bugs in `SKILL.md` -- the reference code is correct, but the skill document either drops behavior (Findings 1, 3) or contains contradictory sequencing (Finding 2).

---

## RALPLAN-DR Summary

### Principles

1. **Fidelity to reference implementation**: The skill doc must faithfully encode the same semantics as `handlers.ts` and `engine.ts`. Where the code enforces a dual-gate or a sequencing rule, the doc must match.
2. **Skills are self-contained protocols**: A skill running as an LLM agent following markdown instructions must contain all logic needed to execute correctly. Ambiguity in the doc becomes a bug at runtime.
3. **Graceful degradation over hard dependencies**: The skill should work in pure in-model mode (no tools required) but should recommend persistence when tools are available, rather than silently losing state.
4. **Minimal diff, maximum clarity**: Fix only what the findings require. Do not restructure the entire document or add features beyond the scope of the three findings.

### Decision Drivers (Top 3)

1. **Correctness**: The skill must not allow a candidate to graduate (reach `completed`) without passing benchmark when benchmark is configured. This is the most critical driver.
2. **Operability under context loss**: LLM context windows compact, conversations interrupt. State that exists only as prose in the conversation can be lost, causing duplicate IDs or broken traces. The fix must address this practically.
3. **Backward compatibility**: The skill is already in use. Changes must not break existing integration patterns (Full Cycle, Refinement Only) documented in the Integration Examples section.

### Viable Options

#### Option A: Pure doc fixes (no external dependencies)
Fix the three contradictions in SKILL.md text only. For Finding 3, strengthen the state-tracking instructions with a structured format the agent must maintain in its responses, but do not require any external tool.

| Pros | Cons |
|------|------|
| Zero new dependencies; skill remains fully portable | State lives only in LLM context; compaction or interruption can still lose it |
| Smallest diff; lowest risk of introducing new issues | No durable session file; long evolution runs (5+ generations) risk context loss |
| Consistent with "skills are markdown protocols" philosophy | Agent must self-enforce ID uniqueness without a persistent registry |

#### Option B: Require skill-runner CLI for state persistence
Make the skill require that the agent calls skill-runner CLI commands (`init`, `score`, `select`, `mutate`, `crossover`, `next-step`) for all state transitions. The skill doc becomes an orchestration guide over the CLI.

| Pros | Cons |
|------|------|
| Fully durable state in `/tmp/reasonforge-{sessionId}.json` | Breaks the "pure skill" model; requires tool access at runtime |
| Duplicate ID detection and status guards are enforced by code | Couples the skill to `packages/skill-runner`; not portable to environments without it |
| Matches the original MCP protocol exactly | Significantly larger SKILL.md rewrite; higher risk of new bugs |

#### Option C (RECOMMENDED): Fix docs + add optional persistent mode section
Fix all three doc contradictions (same as Option A). Additionally, add a new "State Persistence" section that defines two tiers: (1) In-Model State (default) with a structured state block the agent must maintain, and (2) Persistent Mode (optional) that recommends skill-runner CLI calls when the agent has tool access.

| Pros | Cons |
|------|------|
| Fixes all findings with the smallest mandatory diff | Slightly more complex doc (adds ~30 lines for the persistence section) |
| Works in pure-skill mode AND with tool access | Agent must decide which mode to use (but the doc provides clear guidance) |
| In-Model State block mitigates context loss by making state explicit and structured | In-Model mode still cannot survive full context eviction |
| Forward-compatible: persistent mode can be upgraded to MCP later | Two code paths in the doc could confuse a less capable model |

**Why Option C is recommended**: It satisfies all three decision drivers. It fixes correctness (Findings 1, 2) regardless of mode. It addresses operability (Finding 3) with a structured state block that is resilient to partial context loss and offers full durability when tools are available. It preserves backward compatibility by keeping the default mode tool-free.

**Why Option A is insufficient**: It does not adequately address Finding 3. Telling the agent to "record state" without a structured format or persistence mechanism is the exact bug the finding identifies.

**Why Option B is excessive**: It converts a pure skill into a tool-dependent orchestration layer, which contradicts the design intent of the migration. The skill was deliberately moved away from tool dependency.

---

## Work Objectives

Fix all 3 HIGH findings in `SKILL.md` so the skill document is internally consistent and faithful to the reference implementations.

---

## Guardrails

### Must Have
- Phase 2 termination check includes benchmark gate when benchmark is configured
- Phase 4 mutation/crossover sequencing is unambiguous and executable
- State tracking uses a structured, explicit format (not prose hand-waving)
- All existing integration examples remain valid
- State machine diagram matches the Phase 4 text

### Must NOT Have
- No changes to `packages/core/` or `packages/skill-runner/` code (findings are doc-only)
- No restructuring of the 5-phase workflow or state machine beyond what findings require
- No new mandatory tool dependencies in the default mode
- No changes to the scoring_guide.md calibration bands or critique standards

---

## Task Flow

### Step 1: Fix Finding 1 -- Benchmark-gated termination in Phase 2

**What to change**: Lines 160-163 of `SKILL.md` (Phase 2 status transition)

**Current text** (lines 160-163):
```markdown
**After scoring all pending candidates**, evaluate the status transition:

- **If best fitness >= threshold**: Status becomes `completed`. Go to Phase 5.
- **Otherwise**: Status becomes `ready_to_select`. Go to Phase 3.
```

**Required change**: Replace the simple fitness check with a dual-gate check that matches `shouldTerminate()` in `handlers.ts` (lines 51-59):
```markdown
**After scoring all pending candidates**, evaluate the termination condition:

- **If benchmark is configured**: Termination requires BOTH best fitness >= threshold AND the best candidate passes the benchmark check (its answer contains or matches the expected answer).
- **If no benchmark**: Termination requires only best fitness >= threshold.

If the termination condition is met: Status becomes `completed`. Go to Phase 5.
Otherwise: Status becomes `ready_to_select`. Go to Phase 3.
```

**Also update**: The Protocol Summary quick reference (lines 316-317) which has the same bug:
```
  If best fitness >= threshold -> COMPLETED (Phase 5)
```
Must become the dual-gate version.

**Acceptance criteria**:
- Phase 2 text explicitly checks both fitness AND benchmark when benchmark is configured
- Protocol Summary quick reference matches the Phase 2 text
- Config table (line 46) benchmark description remains unchanged (it is already correct)

---

### Step 2: Fix Finding 2 -- Phase 4 mutation/crossover sequencing

**What to change**: Lines 196-243 of `SKILL.md` (Phase 4), line 76 of the state machine diagram, and the Protocol Summary

**Root cause**: The state machine diagram (line 76) says `mutate/crossover registers new candidate -> scoring`. The Phase 4 text says mutation transitions to `scoring` (line 219), then says crossover happens "after mutations" (line 221) -- but by then the status is `scoring`, so crossover would be invalid per the state machine.

**Reference behavior**: `engine.ts` lines 184-221 performs ALL mutations AND crossover within a single generation loop iteration, THEN scores everything. There is no intermediate status transition between mutation and crossover. `handlers.ts` does set status to `scoring` after each mutation (line 242), which means crossover must happen BEFORE any mutation transitions status -- or the design must batch them.

**Required change**: Rewrite Phase 4 to use a batch registration model:
1. While status is `mutating`, the agent performs ALL mutations AND crossover (if applicable)
2. Each new candidate is "registered" (noted as pending) but does NOT individually transition the status
3. After ALL new candidates are registered, status transitions to `scoring`
4. Update the state machine diagram to show: `mutating --[all new candidates registered]--> scoring`

**Acceptance criteria**:
- Phase 4 text makes clear that mutation and crossover both happen while status is `mutating`
- No text says status transitions to `scoring` until ALL new candidates (mutations + crossover) are registered
- State machine diagram line 76 is updated to reflect the batch transition
- Protocol Summary Phase 4 section matches
- The sequencing matches `engine.ts` behavior where both mutation and crossover happen in the same generation before scoring

---

### Step 3: Fix Finding 3 -- Add structured state tracking with optional persistence

**What to change**: Lines 121-126 of `SKILL.md` (Phase 1 Step 1.3) and add a new "State Management" section before the Workflow section

**Root cause**: The skill says "Record generation 0 state" and "the evolution trace begins here" but never defines WHAT to record or WHERE. If the agent's context is compacted, state is lost.

**Required change (Part A)**: Add a new "State Management" section (between "State Machine" and "Workflow") that defines:

1. **In-Model State Block (default)**: A structured markdown/JSON block the agent must include in EVERY response during evolution. This block contains:
   - `session_id`: A unique identifier for the run
   - `generation`: Current generation number
   - `status`: Current state machine status
   - `population`: List of scored candidates with IDs, fitness scores, and benchmark verdict
   - `pending`: List of unscored candidate IDs
   - `config`: The active configuration (threshold, dimensions, limits)
   - `trace`: Per-generation summary (best fitness, actions taken)

   The agent must emit this block after every phase transition. This makes state explicit and recoverable from the last response if context is partially compacted.

2. **Persistent Mode (optional)**: When the agent has access to shell tools, it SHOULD persist state to a JSON file at a known path (e.g., `/tmp/reasonforge-{session_id}.json`). Recommend the skill-runner CLI format for compatibility. This section is advisory, not mandatory.

**Required change (Part B)**: Update Phase 1 Step 1.3 (lines 121-126) to reference the new State Management section and require the agent to emit the initial state block.

**Required change (Part C)**: Add a note to Phase 5 (Termination) that the final result must include the complete evolution trace from the state block.

**Acceptance criteria**:
- A "State Management" section exists with a defined state block schema
- The state block includes all fields needed to resume after context loss: session_id, generation, status, population (with IDs + fitness), pending, config, trace
- Phase 1 Step 1.3 references the state block and requires its emission
- In-Model mode requires NO tools
- Persistent mode is clearly marked as optional and references skill-runner
- Candidate ID uniqueness is addressed (the state block's population + pending lists serve as the registry)

---

### Step 4: Update scoring_guide.md for benchmark-aware scoring

**What to change**: `references/scoring_guide.md` -- add a brief section on benchmark evaluation

**Required change**: Add a short section (after "Composite Score Calculation") explaining:
- When a benchmark is configured, the composite fitness score alone does not determine termination
- The agent must also check whether the best candidate's answer matches the expected benchmark answer
- This is a pass/fail check, not a scored dimension

This ensures the scoring guide is consistent with the updated Phase 2 termination logic.

**Acceptance criteria**:
- scoring_guide.md includes a "Benchmark Evaluation" section
- The section explains the dual-gate: fitness threshold + benchmark pass
- No changes to existing calibration bands or critique standards

---

### Step 5: Validate internal consistency

**What to change**: Full read-through of the updated SKILL.md

**Required checks**:
1. Every status transition mentioned in Phase text matches the state machine diagram
2. The Protocol Summary quick reference matches all Phase descriptions
3. The "Quality Standards" section (lines 289-298) is still accurate after changes
4. Integration Examples (lines 346-382) still work with the updated phases
5. The "When to Use" and "When NOT to Use" sections are unaffected
6. No dangling references to old text that was replaced

**Acceptance criteria**:
- Zero contradictions between state machine, phase descriptions, protocol summary, and quality standards
- All cross-references within the document are valid
- A fresh reader following the document step-by-step would produce correct behavior for all three modes: Full Cycle without benchmark, Full Cycle with benchmark, Refinement Only

---

## ADR: Architecture Decision Record

**Decision**: Option C -- Fix documentation contradictions AND add structured in-model state block with optional persistent mode.

**Drivers**:
1. Correctness: Findings 1 and 2 are unambiguous spec bugs that must be fixed regardless of approach
2. Operability: Finding 3 requires more than "just fix the text" -- the fundamental problem is that state has no defined structure or location
3. Backward compatibility: Cannot introduce mandatory tool dependencies without breaking the skill's portability

**Alternatives considered**:
- Option A (pure doc fixes): Rejected because it does not adequately address Finding 3's state persistence concern. Telling the agent to "record state" without a schema is the same class of bug.
- Option B (require skill-runner): Rejected because it reverses the design intent of the CLI-to-Skills migration. The skill was deliberately made tool-independent.

**Why chosen**: Option C is the minimum viable fix that addresses all three findings without introducing new dependencies. The structured state block makes in-model state explicit (addressing Finding 3) while the optional persistent mode provides an upgrade path. Findings 1 and 2 are straightforward doc corrections.

**Consequences**:
- SKILL.md grows by approximately 40-60 lines (State Management section + expanded Phase 2/4 text)
- Agents following the skill must now emit a state block after each phase transition (new requirement)
- The state block format becomes a soft contract -- future MCP integration can read it
- In-model state still cannot survive full context eviction (acknowledged limitation)

**Follow-ups**:
- Consider adding the state block schema to `references/` as a separate file for programmatic validation
- If MCP server is updated, the persistent mode section should reference the MCP tool names instead of CLI commands
- Monitor whether agents reliably emit the state block; if not, consider making persistent mode the default

---

## Success Criteria

1. All three HIGH findings are resolved with no regressions
2. The skill document is internally consistent (state machine = phase text = protocol summary)
3. The skill works in pure in-model mode without any tool dependencies
4. When benchmark is configured, termination requires both fitness threshold AND benchmark pass
5. Phase 4 mutation and crossover can both execute without status contradiction
6. State has a defined structure that an agent can emit and a reader can parse
