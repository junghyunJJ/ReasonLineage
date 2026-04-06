# ReasonForge: Evolutionary Reasoning

Improve answers through iterative evolutionary cycles: generate diverse candidates, critique them rigorously, select the best, mutate to improve, and repeat until a quality threshold is met.

Usage: `/reasonforge <question or problem to reason about>`

## Configuration

- **threshold**: 0.85 (fitness score to stop evolution)
- **populationLimit**: 5 (max candidates per generation)
- **generationLimit**: 3 (max evolution cycles)
- **dimensions**: logicalConsistency (0.5), evidenceGrounding (0.2), solutionUsefulness (0.3)

The CLI is at: `packages/skill-runner/src/cli.ts`
Run via: `npx tsx packages/skill-runner/src/cli.ts <subcommand> '<json>'`

---

## Phase 1: Analyze the Question

Before generating candidates, analyze the question to determine appropriate evaluation dimensions.

For most questions, use the defaults: `logicalConsistency`, `evidenceGrounding`, `solutionUsefulness`.

For specialized domains, consider adding dimensions:
- Scientific questions: add `technicalAccuracy`
- Creative tasks: add `creativity`, `originality`
- Ethical dilemmas: add `ethicalAlignment`

Adjust weights so they sum to ~1.0. Set the threshold, populationLimit, and generationLimit.

---

## Phase 2: Generate Initial Population

Use the Agent tool to spawn a **Generator** subagent that produces 3 diverse candidate answers.

**Generator system prompt:**
> You are a creative problem-solver. Generate 3 diverse candidate answers to the given question. Each candidate should take a genuinely different approach or perspective. Include at least one unconventional answer. Do NOT critique or hedge — just generate bold, distinct answers. Return JSON: `{"candidates": [{"id": "seed-1", "answer": "..."}, {"id": "seed-2", "answer": "..."}, {"id": "seed-3", "answer": "..."}]}`

After receiving the candidates, initialize the session:

```bash
npx tsx packages/skill-runner/src/cli.ts init '{"threshold": 0.85, "populationLimit": 5, "generationLimit": 3, "weights": {"logicalConsistency": 0.5, "evidenceGrounding": 0.2, "solutionUsefulness": 0.3}, "candidates": [{"id": "seed-1", "answer": "..."}, ...]}'
```

Save the returned `sessionId` for all subsequent calls.

---

## Phase 3: Critique & Score

Call `next-step` to check status and get pending candidates:

```bash
npx tsx packages/skill-runner/src/cli.ts next-step '{"sessionId": "SESSION_ID"}'
```

For each pending candidate, use the Agent tool to spawn a **Critic** subagent.

**Critic system prompt:**
> You are a rigorous, skeptical evaluator. Your job is to find flaws, not to praise. Score the candidate answer on each dimension from 0.0 to 1.0. Be strict: a score of 0.9+ means genuinely excellent with specific supporting evidence. A score below 0.5 means significant problems. Provide 1-3 specific critique points explaining weaknesses. Return JSON: `{"scores": {"logicalConsistency": 0.0-1.0, "evidenceGrounding": 0.0-1.0, "solutionUsefulness": 0.0-1.0}, "critique": ["point 1", "point 2"]}`

Then submit the score:

```bash
npx tsx packages/skill-runner/src/cli.ts score '{"sessionId": "SESSION_ID", "candidateId": "CANDIDATE_ID", "scores": {"logicalConsistency": 0.8, ...}, "critique": ["point 1", ...]}'
```

After scoring all pending candidates, call `next-step` again:
- If `status` is `"completed"` → go to **Phase 5**
- If `status` is `"ready_to_select"` → go to **Phase 4**

---

## Phase 4: Evolve

### Selection

```bash
npx tsx packages/skill-runner/src/cli.ts select '{"sessionId": "SESSION_ID", "survivorCount": 2}'
```

### Mutation

Use the Agent tool to spawn a **Mutator** subagent for the best surviving candidate.

**Mutator system prompt:**
> You are improving an existing answer based on specific critique points. Address each critique item directly. Preserve what already works well. Make the answer stronger, more precise, and better supported. Do NOT start over — refine and strengthen. Return JSON: `{"answer": "improved answer text"}`

Pass to the Mutator: the best candidate's answer text and its critique points.

Then register the mutation:

```bash
npx tsx packages/skill-runner/src/cli.ts mutate '{"sessionId": "SESSION_ID", "parentId": "BEST_ID", "candidateId": "mut-gen-N", "answer": "improved answer"}'
```

### Crossover (optional)

If 2+ survivors exist, optionally spawn a **Crossover** subagent to combine the top 2:

> Combine the strongest elements of both candidate answers into one superior answer. Take the best reasoning from each. Return JSON: `{"answer": "combined answer text"}`

```bash
npx tsx packages/skill-runner/src/cli.ts crossover '{"sessionId": "SESSION_ID", "parentIds": ["id-a", "id-b"], "candidateId": "cross-gen-N", "answer": "combined answer"}'
```

After registering mutations/crossovers, return to **Phase 3** to score the new candidates.

---

## Phase 5: Present Result

Call `next-step` one final time to get the final status:

```bash
npx tsx packages/skill-runner/src/cli.ts next-step '{"sessionId": "SESSION_ID"}'
```

Present the result to the user:

1. **Final answer**: The `bestAnswer` from the response
2. **Fitness score**: The `bestFitness` value
3. **Generations**: How many evolution cycles were run
4. **How it was reached**: Whether threshold was met or generation limit reached
5. **Evolution trace**: Brief summary of how the answer improved across generations

Clean up the session file when done (it's in `/tmp/reasonforge-SESSION_ID.json`).

---

## Important Rules

- Always call `next-step` after scoring all candidates to check status before proceeding
- Never skip Phase 3 (scoring) — every new candidate must be scored before selection
- The Critic should be genuinely strict — inflated scores defeat the purpose of evolution
- If `status` becomes `"completed"` at any point, skip directly to Phase 5
- Use unique candidate IDs: `seed-N` for initial, `mut-gen-N` for mutations, `cross-gen-N` for crossovers
