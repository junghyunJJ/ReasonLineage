# Plan: Convert ReasonForge from MCP Server to Claude Code Skill

**Date:** 2026-04-03
**Status:** Draft v2 - Revised per Architect + Critic feedback
**Estimated Complexity:** MEDIUM

---

## RALPLAN-DR Summary

### Principles
1. **Preserve the core engine** -- `@reasonforge/core` is well-designed and battle-tested; the Skill wraps it, never reimplements it.
2. **Preserve the proven state machine** -- `tools.ts` contains ~340 lines of correct, tested evolutionary mechanics (scoring, selection, mutation registration, termination). Port this logic; do not reinvent it.
3. **Skill = protocol instructions, not code** -- The `.md` file teaches Claude *how* to run the evolutionary loop; a stateful CLI handles computation and state transitions.
4. **Cognitive separation via Agent tool** -- Generator, Critic, and Mutator roles get different system prompts to mitigate self-critique bias.
5. **YAGNI** -- Phase 1 is single-model self-critique with structured dimensions. Cross-model is future work.

### Decision Drivers
1. **Runner design** -- The `mutate` callback in `runReasonForgeCycle()` creates NEW candidates that are immediately scored by `judge`. Pre-computed scores cannot work because the new candidate IDs do not exist when the runner starts. This eliminates any single-shot approach that pre-feeds scores.
2. **State management** -- The MCP's state machine (status transitions: `scoring` -> `ready_to_select` -> `mutating` -> `scoring`) is correct. Only the *storage layer* (in-memory Map + TTL/GC) is problematic.
3. **Agent separation** -- Claude must provide all LLM intelligence (generation, critique, mutation) between CLI calls. The CLI handles only computation and state.

### Viable Options

#### Option A: Single-Shot Runner with Pre-Computed Callbacks (INVALIDATED)

**Why invalidated:**
At `engine.ts:186`, the `mutate` callback creates a new `Candidate` with a new ID and answer. At `engine.ts:197`, `scoreCandidate()` immediately calls `input.judge(mutated)` on this NEW candidate. Since the candidate did not exist when the runner started, pre-computed scores cannot contain its ID. This means:
- Setting `generationLimit=0` avoids the crash but reduces the engine to a ~15-line fitness calculator (just `calculateFitness()`)
- The "hybrid" approach of driving the outer loop from the Skill while calling the runner per-generation still hits the same problem: `mutate` and `judge` are called within the same synchronous generation loop inside `runReasonForgeCycle()`
- There is no way to inject LLM responses into callbacks that execute inside a Node.js process without an IPC mechanism, which would be more complex than the stateful CLI

#### Option B: Stateful CLI (ADOPTED)

Extract `tools.ts`'s state machine logic into a CLI with file-based state. Each CLI subcommand maps 1:1 to a current MCP tool handler.

**Pros:**
- Preserves the PROVEN state machine from `tools.ts` (340 lines of tested logic)
- Replaces only the bad layer (in-memory Map + MCP transport) with simple JSON files in `/tmp`
- The Skill `.md` orchestrates by calling CLI subcommands via Bash tool
- Claude provides all LLM intelligence via Agent tool between CLI calls
- This is exactly what the MCP did, minus the transport overhead
- ~200 lines of runner code (mostly ported from `tools.ts`)

**Cons:**
- State persists across multiple Bash calls (but this is inherent to any multi-step evolutionary process)
- JSON file I/O adds trivial overhead vs. in-memory Map
- Slightly more CLI surface area than a single-shot runner (6 subcommands vs. 1)

**Why these cons are acceptable:**
- File-based state is actually MORE robust than in-memory state (survives process crashes)
- The 6 subcommands are a 1:1 port of already-working handlers, not new logic
- The Skill `.md` orchestrates the subcommand sequence, so Claude never has to guess the order

---

## Context

### Current State
- `@reasonforge/core`: Pure TS library. `runReasonForgeCycle(input)` accepts async callbacks for `judge`, `critique`, `mutate`, `crossover`. Returns `{status, finalAnswer, finalFitness, finalCandidate, events}`. The callbacks are invoked *within* the engine's generation loop, making it impossible to inject LLM responses without IPC.
- `@reasonforge/core` exports: `calculateFitness()`, `evaluateBenchmarkAnswer()`, `createCandidate()`, `defaultJudgeWeights` -- all usable standalone without `runReasonForgeCycle()`.
- `@reasonforge/mcp`: 6 MCP tool handlers in `tools.ts` that form a state machine wrapper around manual phase transitions. Session storage in `session.ts` uses in-memory `Map` with TTL/GC. The tool handlers are well-designed; the transport/storage layer is what failed.
- No `.claude/` directory exists yet. No existing Skill infrastructure.

### Target State
- A Claude Code Skill (`.md` file) at `.claude/commands/reasonforge.md` that Claude can invoke
- A stateful CLI at `packages/skill-runner/` with 6 subcommands ported from `tools.ts`
- State stored as JSON files in `/tmp/reasonforge-{sessionId}.json`
- The Skill orchestrates the evolutionary loop, calling CLI subcommands via Bash and Agent tool for LLM work
- The MCP server remains intact (not deleted) but is effectively superseded

---

## Work Objectives

1. Create a new `packages/skill-runner` package with a stateful CLI that ports `tools.ts` state machine to file-based storage
2. Create the Skill `.md` file with the 5-phase evolutionary reasoning protocol
3. Write tests for the CLI (unit tests for each subcommand + one integrated end-to-end test)
4. Add minimal documentation

---

## Guardrails

### Must Have
- CLI uses `calculateFitness()` and `evaluateBenchmarkAnswer()` from `@reasonforge/core` (no reimplementation of scoring)
- CLI state machine preserves the status transitions from `tools.ts`: `scoring` -> `ready_to_select` -> `mutating` -> `scoring` -> ... -> `completed`
- Skill uses structured dimension-based scoring (not vague "is this good?")
- Skill specifies different system prompt contexts for Generator vs Critic vs Mutator roles
- State file JSON schema is documented and stable
- Tests cover the full Skill -> CLI -> Result flow (at least one integrated scenario)

### Must NOT Have
- Cross-model judging (Phase 2 -- future)
- Python code (the protocol pattern is extractable but we don't build the Python adapter)
- Deletion or modification of `@reasonforge/mcp` (it stays as-is)
- In-memory session storage, TTL, or garbage collection (replaced by file-based state)
- Direct calls to `runReasonForgeCycle()` (its callback model is incompatible with the Skill's inter-process LLM calls)
- Web dashboard integration changes

---

## Task Flow

```
Step 1: Skill Runner Package (Stateful CLI)
    |
    v
Step 2: Skill Markdown File (5-Phase Protocol)
    |
    v
Step 3: Tests (Unit + Integrated End-to-End)
    |
    v
Step 4: Documentation & Integration
```

---

## Detailed TODOs

### Step 1: Create `packages/skill-runner` -- Stateful CLI

**Files to create:**
- `packages/skill-runner/package.json`
- `packages/skill-runner/tsconfig.json`
- `packages/skill-runner/src/cli.ts` (CLI entry point with subcommand dispatch)
- `packages/skill-runner/src/state.ts` (file-based state management, replaces `session.ts`)
- `packages/skill-runner/src/handlers.ts` (ported from `tools.ts`, uses file-based state)
- `packages/skill-runner/src/index.ts` (library exports for testing)

**CLI subcommands (map 1:1 to MCP tool handlers):**

```
npx tsx packages/skill-runner/src/cli.ts init       '{"threshold":0.85,...}'
npx tsx packages/skill-runner/src/cli.ts score      '{"sessionId":"...","candidateId":"...","scores":{...},"critique":[...]}'
npx tsx packages/skill-runner/src/cli.ts select     '{"sessionId":"...","survivorCount":2}'
npx tsx packages/skill-runner/src/cli.ts mutate     '{"sessionId":"...","parentId":"...","candidateId":"...","answer":"..."}'
npx tsx packages/skill-runner/src/cli.ts crossover  '{"sessionId":"...","parentIds":["a","b"],"candidateId":"...","answer":"..."}'
npx tsx packages/skill-runner/src/cli.ts next-step  '{"sessionId":"..."}'
```

**State file schema (`/tmp/reasonforge-{sessionId}.json`):**

```json
{
  "id": "uuid",
  "config": {
    "threshold": 0.85,
    "populationLimit": 5,
    "generationLimit": 3,
    "weights": { "logicalConsistency": 0.5, "evidenceGrounding": 0.2, "solutionUsefulness": 0.3 },
    "benchmark": null
  },
  "generation": 0,
  "population": [
    {
      "id": "candidate-1",
      "answer": "...",
      "logicalConsistency": 0.8,
      "evidenceGrounding": 0.7,
      "solutionUsefulness": 0.9,
      "scores": { "logicalConsistency": 0.8, "evidenceGrounding": 0.7, "solutionUsefulness": 0.9 },
      "fitness": 0.81,
      "critique": ["Lacks evidence for claim X"],
      "benchmarkVerdict": { "passed": true, "expectedAnswer": "", "normalizedAnswer": "" }
    }
  ],
  "pendingCandidates": [
    { "id": "candidate-2", "answer": "..." }
  ],
  "status": "scoring",
  "createdAt": 1712150400000
}
```

**State management (`state.ts`) -- replaces `session.ts`:**
- `createSessionFile(config, seedCandidates) -> SessionState` -- writes `/tmp/reasonforge-{uuid}.json`
- `readSessionFile(sessionId) -> SessionState | null` -- reads and parses the JSON file
- `writeSessionFile(sessionId, state) -> void` -- overwrites the JSON file
- `deleteSessionFile(sessionId) -> boolean` -- removes the file
- No TTL, no GC, no MAX_SESSIONS, no in-memory Map
- Session files are cleaned up by the Skill at the end of a run (or by OS `/tmp` cleanup)

**Handler porting strategy (`handlers.ts`) -- from `tools.ts`:**
- `handleInit` (from `handleStartSession`): Creates session file, stores seed candidates as pending
- `handleScore` (from `handleScoreCandidate`): Reads state, scores candidate using `calculateFitness()`, writes state. Auto-transitions to `ready_to_select` when all pending scored. Checks termination via `shouldTerminate()`.
- `handleSelect` (from `handleSelect`): Reads state, sorts population, keeps top N survivors, increments generation, transitions to `mutating`, writes state.
- `handleMutate` (from `handleMutate`): Reads state, validates parent exists in population, registers new candidate in `pendingCandidates`, transitions to `scoring`, writes state.
- `handleCrossover` (from `handleCrossover`): Same pattern as mutate but validates two parents.
- `handleNextStep` (from `handleNextStep`): Reads state, determines suggested next action based on current status. Returns status + suggestion JSON.

**Key differences from `tools.ts`:**
- Returns plain JSON objects to stdout (no MCP `content` wrapper)
- Uses `fs.readFileSync`/`fs.writeFileSync` instead of `Map.get`/`Map.set`
- No `lastAccessedAt` tracking (not needed without TTL)
- Error handling: prints JSON `{"error": "message"}` to stderr, exits with code 1

**Acceptance Criteria:**
- [ ] Each subcommand reads/writes state from `/tmp/reasonforge-{id}.json`
- [ ] `init` creates a session file and returns `{sessionId, candidateCount}`
- [ ] `score` correctly calculates fitness using `@reasonforge/core`'s `calculateFitness()`
- [ ] `score` auto-transitions to `ready_to_select` when all pending candidates are scored
- [ ] `score` auto-transitions to `completed` when threshold is met
- [ ] `select` sorts population, keeps survivors, increments generation, transitions to `mutating`
- [ ] `mutate` registers a new candidate in `pendingCandidates` and transitions to `scoring`
- [ ] `next-step` returns correct suggested action for each status phase
- [ ] Invalid operations (e.g., scoring in `mutating` phase) produce clear error messages
- [ ] Package builds without errors (`pnpm build` in skill-runner)
- [ ] Runner is ~200 lines total (handlers + state), not counting CLI dispatch boilerplate

---

### Step 2: Create the Skill Markdown File

**Files to create:**
- `.claude/commands/reasonforge.md`

**What the Skill does:**

The Skill is a structured protocol document that instructs Claude on how to run the ReasonForge evolutionary reasoning cycle. It orchestrates 5 phases, calling CLI subcommands for computation and Agent tool for LLM intelligence.

**Phase-by-phase Skill flow:**

**Phase 1: Analyze**
- Determine evaluation dimensions for this specific question
- Default to `logicalConsistency`, `evidenceGrounding`, `solutionUsefulness`
- Allow dynamic dimensions based on question type (e.g., add `creativity` for open-ended problems)
- Set config: threshold (default 0.85), populationLimit (default 5), generationLimit (default 3)

**Phase 2: Generate Initial Population**
- Use Agent tool to spawn a Generator subagent with system prompt: "You are a creative problem-solver. Generate a diverse, novel answer. Do NOT critique or hedge."
- Generate N=3 diverse candidate answers, each with a unique ID
- Call CLI: `cli.ts init '{"threshold":0.85, "candidates":[{id,answer},...], ...}'`
- Capture the returned `sessionId`

**Phase 3: Score (Critique Loop)**
- Call CLI: `cli.ts next-step '{"sessionId":"..."}'` to get current status and pending candidates
- For each pending candidate:
  - Use Agent tool to spawn a Critic subagent with system prompt: "You are a rigorous evaluator. Score ONLY on the specified dimensions. Be strict. A score of 0.9+ means genuinely excellent with specific evidence."
  - Critic returns `{scores: {dimension: 0-1, ...}, critique: ["point 1", ...]}`
  - Call CLI: `cli.ts score '{"sessionId":"...","candidateId":"...","scores":{...},"critique":[...]}'`
- After all candidates scored, call `next-step` to check status:
  - If `status: "completed"` (threshold met) -> go to Phase 5
  - If generation limit reached -> go to Phase 5
  - If `status: "ready_to_select"` -> go to Phase 4

**Phase 4: Evolve**
- Call CLI: `cli.ts select '{"sessionId":"...","survivorCount":2}'`
- Use Agent tool to spawn a Mutator subagent with system prompt: "You are improving an existing answer based on specific critique points. Address each critique item. Do not discard what works."
  - Mutator receives: best candidate's answer + its critique points
  - Mutator returns: improved answer text
- Call CLI: `cli.ts mutate '{"sessionId":"...","parentId":"best-id","candidateId":"mutated-gen-N","answer":"improved text"}'`
- Optionally: if 2+ survivors, spawn Crossover subagent to combine top 2
  - Call CLI: `cli.ts crossover '{"sessionId":"...","parentIds":["a","b"],"candidateId":"cross-gen-N","answer":"combined text"}'`
- Return to Phase 3 (score the new candidates)

**Phase 5: Present Result**
- Call CLI: `cli.ts next-step '{"sessionId":"..."}'` to get final status
- Output the final answer with fitness score and generation count
- Include the evolutionary trace (which candidates were tried, how fitness improved per generation)
- Clean up: delete the session file

**Acceptance Criteria:**
- [ ] File exists at `.claude/commands/reasonforge.md`
- [ ] Contains clear trigger/description that Claude Code recognizes as a slash command
- [ ] Specifies the 5-phase protocol with CLI subcommand calls and Agent tool delegation
- [ ] Includes distinct system prompts for Generator, Critic, and Mutator roles
- [ ] References the CLI script path correctly for Bash invocation
- [ ] Includes configurable parameters (threshold, generations, population size, dimensions)
- [ ] Each phase clearly states which CLI subcommand(s) to call and with what arguments
- [ ] Includes cleanup step to delete session file on completion
- [ ] Works when invoked as `/reasonforge "What is the best approach to X?"`

---

### Step 3: Tests (Unit + Integrated End-to-End)

**Files to create:**
- `packages/skill-runner/tests/handlers.test.ts` (unit tests for each handler)
- `packages/skill-runner/tests/integration.test.ts` (end-to-end CLI test)

**Unit test cases (`handlers.test.ts`):**
1. **init** -- Create session with 3 candidates, verify state file exists with correct shape, status is `scoring`, pendingCandidates has 3 entries
2. **score -- happy path** -- Score all 3 candidates, verify fitness calculated correctly via `calculateFitness()`, verify auto-transition to `ready_to_select`
3. **score -- threshold met** -- Score a candidate above threshold, verify auto-transition to `completed`
4. **score -- phase guard** -- Attempt to score in `mutating` phase, verify error
5. **select** -- Select 2 survivors from 3, verify generation incremented, population trimmed, status is `mutating`
6. **select -- generation limit** -- Attempt select when generation >= generationLimit, verify error
7. **mutate** -- Register a mutated candidate, verify it appears in pendingCandidates, status transitions to `scoring`
8. **mutate -- duplicate ID** -- Attempt mutate with existing candidate ID, verify error
9. **crossover** -- Register a crossover candidate from two parents, verify pendingCandidates updated
10. **next-step** -- Test each status branch: `scoring` (suggests score), `ready_to_select` (suggests select), `mutating` (suggests mutate), `completed` (no suggestion)
11. **custom dimensions** -- Use `{creativity: 0.5, depth: 0.3, clarity: 0.2}` weights, verify fitness calculation matches
12. **benchmark integration** -- Provide a benchmark case, verify `benchmarkVerdict` is populated on scored candidates

**Integrated end-to-end test (`integration.test.ts`):**

This test simulates the full Skill flow by calling CLI subcommands in sequence, WITHOUT any LLM. It provides hardcoded answers and scores to exercise the complete lifecycle:

```
1. init with 3 candidates (question: "What is 2+2?")
2. score candidate-1 (fitness ~0.7)
3. score candidate-2 (fitness ~0.6)
4. score candidate-3 (fitness ~0.5)
5. next-step -> expect status "ready_to_select"
6. select (survivorCount: 2) -> expect generation=1, 2 survivors
7. mutate (parentId: candidate-1, new answer: "Four, because...")
8. score the mutation (fitness ~0.9)
9. next-step -> expect status "completed" (threshold met)
10. Verify final state: status=completed, best fitness >= 0.85
11. Verify session file can be deleted (cleanup)
```

**Acceptance Criteria:**
- [ ] All unit tests pass via `pnpm test` in `packages/skill-runner`
- [ ] The integrated test exercises the full `init -> score -> select -> mutate -> score -> completed` flow
- [ ] Tests use `@reasonforge/core`'s actual `calculateFitness()` (not mocks of core logic)
- [ ] Tests can run without any LLM or network access (pure computation + file I/O)
- [ ] Tests clean up their `/tmp/reasonforge-*.json` files after each test

---

### Step 4: Documentation & Integration

**Files to create/modify:**
- `packages/skill-runner/README.md` -- Usage, CLI subcommands, state file schema, architecture
- `pnpm-workspace.yaml` -- Add `packages/skill-runner` to workspace (if not already covered by glob)

**Files to verify:**
- `.claude/commands/reasonforge.md` -- Ensure it is discoverable by Claude Code
- Root `package.json` -- No changes needed (pnpm workspace glob likely covers it)

**Documentation contents:**
- What ReasonForge Skill does (1 paragraph)
- How to invoke: `/reasonforge "your question here"`
- CLI subcommand reference (init, score, select, mutate, crossover, next-step)
- State file JSON schema
- Architecture diagram: Skill (orchestrator) -> Agent tool (Generator/Critic/Mutator) -> CLI (computation + state)
- Comparison with MCP approach (why Skill + CLI is preferred)

**Acceptance Criteria:**
- [ ] `pnpm-workspace.yaml` includes `packages/skill-runner` (verify the glob pattern `packages/*` already covers it)
- [ ] `pnpm install` succeeds from repo root with the new package
- [ ] `pnpm build` succeeds across all packages
- [ ] README documents all 6 CLI subcommands with input/output examples
- [ ] The Skill is listed when running Claude Code's slash command discovery

---

## Success Criteria (Overall)

1. Running `/reasonforge "Should I use a monorepo or polyrepo?"` in Claude Code triggers the 5-phase evolutionary reasoning cycle
2. The cycle produces a final answer that went through at least 1 generation of critique -> select -> mutate -> re-score
3. Each CLI subcommand works standalone: `npx tsx packages/skill-runner/src/cli.ts <subcommand> '<json>'` produces valid JSON
4. The integrated end-to-end test passes, covering the full `init -> score -> select -> mutate -> score -> completed` flow
5. All unit tests pass (12 cases covering each handler + edge cases)
6. No changes to `@reasonforge/core` or `@reasonforge/mcp`
7. The Skill uses Agent tool to separate Generator, Critic, and Mutator cognitive roles
8. State is persisted as JSON files in `/tmp` -- no in-memory state, no TTL, no GC

---

## ADR: Stateful CLI Over Single-Shot Runner

**Decision:** Convert ReasonForge from MCP server to Claude Code Skill with a stateful CLI that ports the MCP's proven state machine to file-based storage.

**Drivers:**
1. The `mutate` callback in `runReasonForgeCycle()` creates NEW candidates that are immediately scored by `judge` within the same execution context. Pre-computed scores cannot work because the new candidate IDs do not exist when the runner starts. This eliminates any single-shot approach.
2. The MCP's `tools.ts` state machine (~340 lines) is correct and well-tested. It decomposes evolutionary mechanics into 6 discrete operations with proper phase guards. This logic should be preserved, not reimplemented.
3. The MCP's failure was in its transport/storage layer (`session.ts`: in-memory Map, TTL, GC, MAX_SESSIONS), NOT in its state machine logic.
4. Skills are native to Claude Code, the primary consumption environment. They enable Agent tool for cognitive separation (generator != critic).

**Alternatives Considered:**
- **Option A: Single-Shot Runner with pre-computed callbacks** -- INVALIDATED. At `engine.ts:186`, `mutate` creates a new candidate; at `engine.ts:197`, `scoreCandidate()` calls `judge` on the new candidate. The pre-provided scores don't contain the new candidate's ID. Setting `generationLimit=0` avoids this but reduces the engine to a trivial fitness calculator, making `runReasonForgeCycle()` unnecessary.
- **Keep MCP, fix loading issues** -- Rejected because the architecture is fundamentally misaligned: MCP is for tools that add capabilities Claude lacks, but here Claude IS the intelligence and MCP is just bookkeeping.

**Why Chosen:** The Stateful CLI separates the MCP into two layers and replaces only the bad one:
- **Layer 1 (preserved):** `tools.ts` state machine -- correct decomposition of evolutionary mechanics into 6 discrete operations with proper phase guards and auto-transitions.
- **Layer 2 (replaced):** `session.ts` in-memory Map + MCP transport -- replaced with `fs.readFileSync`/`fs.writeFileSync` to JSON files in `/tmp`.

The Skill `.md` orchestrates the same sequence Claude used to drive via MCP tools, but now via Bash calls to CLI subcommands. All LLM intelligence (generation, critique, mutation) happens via Agent tool between CLI calls.

**Consequences:**
- MCP server becomes legacy (not deleted, just superseded)
- The web dashboard (`apps/web`) already bypasses MCP and calls core directly -- no changes needed there
- State files in `/tmp` are ephemeral and cleaned up by the Skill or OS
- The CLI is testable without any LLM (pure computation + file I/O)

**Follow-ups:**
- Phase 2: Cross-model critique via Agent tool model parameter
- Python DeepAgents adapter: Extract the Skill protocol into a middleware pattern
- Deprecation notice on `@reasonforge/mcp` README

---

## Resolved Questions

1. **Open Question 5 (was blocking):** "Should the runner's `mutate` callback be a true no-op?" -- RESOLVED. The `mutate` callback in `runReasonForgeCycle()` is REAL: it creates a new candidate that is immediately scored. This is precisely why the single-shot runner cannot work. In the Stateful CLI approach, mutation is handled by the Skill (via Agent tool -> Mutator subagent) and registered via `cli.ts mutate` -- no callback is involved.

2. **Why not just use `calculateFitness()` directly?** -- The CLI does use `calculateFitness()` from `@reasonforge/core`. It does NOT use `runReasonForgeCycle()`. The value the CLI adds beyond raw `calculateFitness()` is: state machine transitions, phase guards, termination checks, population management, and `next-step` suggestions. These are the same things `tools.ts` provided.

3. **State cleanup:** Session files are deleted by the Skill at the end of Phase 5. If the Skill is interrupted, `/tmp` cleanup handles stale files. No TTL/GC needed.
