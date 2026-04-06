# @reasonforge/skill-runner

Stateful CLI for ReasonForge evolutionary reasoning. Ports the MCP server's proven state machine to file-based storage for use with the Claude Code Skill.

## Architecture

```
Skill .md (orchestrator)
  ├── Agent tool: Generator / Critic / Mutator
  └── Bash: CLI subcommands (this package)
        ├── Uses @reasonforge/core's calculateFitness()
        ├── State machine from MCP's tools.ts
        └── State: /tmp/reasonforge-{id}.json
```

## CLI Subcommands

All subcommands accept JSON as the second argument and output JSON to stdout.

```bash
npx tsx packages/skill-runner/src/cli.ts <subcommand> '<json>'
```

### `init` — Create a session

```bash
npx tsx packages/skill-runner/src/cli.ts init '{
  "threshold": 0.85,
  "populationLimit": 5,
  "generationLimit": 3,
  "weights": {"logicalConsistency": 0.5, "evidenceGrounding": 0.2, "solutionUsefulness": 0.3},
  "candidates": [{"id": "seed-1", "answer": "..."}, {"id": "seed-2", "answer": "..."}]
}'
```

**Output:** `{"sessionId": "uuid", "candidateCount": 2, "message": "..."}`

### `score` — Score a candidate

```bash
npx tsx packages/skill-runner/src/cli.ts score '{
  "sessionId": "...",
  "candidateId": "seed-1",
  "scores": {"logicalConsistency": 0.8, "evidenceGrounding": 0.7, "solutionUsefulness": 0.9},
  "critique": ["Good logic", "Needs more evidence"]
}'
```

**Output:** `{"candidateId": "seed-1", "fitness": 0.81, "benchmarkPassed": true, "populationScoredCount": 1, "totalPending": 1}`

### `select` — Select survivors

```bash
npx tsx packages/skill-runner/src/cli.ts select '{"sessionId": "...", "survivorCount": 2}'
```

**Output:** `{"generation": 1, "survivors": [...], "eliminated": [...]}`

### `mutate` — Register a mutation

```bash
npx tsx packages/skill-runner/src/cli.ts mutate '{
  "sessionId": "...",
  "parentId": "seed-1",
  "candidateId": "mut-gen-1",
  "answer": "improved answer text"
}'
```

### `crossover` — Register a crossover

```bash
npx tsx packages/skill-runner/src/cli.ts crossover '{
  "sessionId": "...",
  "parentIds": ["seed-1", "seed-2"],
  "candidateId": "cross-gen-1",
  "answer": "combined answer text"
}'
```

### `next-step` — Check status and get guidance

```bash
npx tsx packages/skill-runner/src/cli.ts next-step '{"sessionId": "..."}'
```

**Output:** Status, best candidate, fitness, threshold check, and suggested next action.

## State File

Sessions are stored as JSON in `/tmp/reasonforge-{sessionId}.json`. Cleaned up by the Skill on completion or by OS temp file management.

## Why Skill + CLI over MCP?

The MCP server's state machine logic is correct and well-tested. But the MCP transport layer (in-memory sessions, TTL, GC) added unnecessary complexity and failed to load reliably. This CLI preserves the state machine while replacing the transport with simple file I/O.
