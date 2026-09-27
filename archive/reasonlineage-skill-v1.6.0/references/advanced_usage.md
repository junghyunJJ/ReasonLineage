# Advanced Usage

## Self-Critique Mitigation

This skill uses same-model self-critique, which has known limitations. The following mitigations are built into the protocol:

1. **Persona separation**: Three distinct personas -- Strict Evaluator (Phase 2), Targeted Refiner (Phase 4 mutation), and Crossover Synthesizer (Phase 4 crossover) -- use fundamentally different instructions. This creates cognitive separation even within the same model.

2. **Structured dimension scoring**: Scoring on specific dimensions (e.g., "rate evidence coverage 0-1") produces more reliable evaluations than holistic judgments ("is this good?").

3. **Conservative calibration**: The scoring guide explicitly anchors 0.9+ as exceptional and requires justification. This combats score inflation.

4. **Selection pressure**: Even with noisy self-evaluation, relative ranking (A better than B) is more reliable than absolute scoring. The evolutionary selection mechanism exploits this.

5. **Critique-driven mutation**: Mutations must address specific critique points, not just rephrase. This forces directional improvement.

6. **Crossover diversity**: Combining two distinct survivors introduces structural variation that single-parent mutation cannot achieve. This helps escape local optima.

**Known limitation**: Same-model critique cannot identify unknown unknowns -- flaws the model consistently overlooks. For higher-stakes applications, consider using different models for generation vs. critique.

When Multi-Backend Mode is on, the skill first probes which roster CLIs actually run on this machine (`<cli> --help`). N=1 falls back to this single-agent loop for the rest of the run. N>=2 sizes population and the recusal panel from those backends. Those numbers last for that run only; they are not written back into the shared skill file. See **Runtime roster probe** in `SKILL.md`.

---

## Hybrid Mode (Recommended for High-Stakes Use)

For high-stakes tasks, delegate arithmetic and state management to the skill-runner CLI while the LLM handles creative work (generation, critique, mutation):

1. **LLM generates/mutates/critiques** — the creative, language-dependent parts
2. **CLI computes fitness, enforces state transitions, manages population** — the precise, deterministic parts

```
npx reasonlineage init --weights '{"accuracy":0.4,"clarity":0.3,"depth":0.3}' --threshold 0.75
npx reasonlineage score --session <id> --candidate <id> --scores '{"accuracy":0.8,"clarity":0.6,"depth":0.7}' --critique '["weakness 1"]'
npx reasonlineage select --session <id>
npx reasonlineage mutate --session <id> --parent <id> --candidate <id> --answer '...'
npx reasonlineage next-step --session <id>
```

This recovers programmatic guarantees (exact fitness calculation, state machine enforcement, population limit checks) while preserving the skill's creative strengths. See `packages/skill-runner/` for the CLI implementation.

---

## Related Skills

- `drug-target-hypothesis` -- Drug target hypothesis generation with UCB scoring. Uses reasonlineage for iterative refinement when hypothesis quality is below threshold.
- `hypothesis-generation` -- General scientific hypothesis generation with LaTeX PDF output and 8-step manual workflow.
- `hypogenic` -- Automated LLM-driven hypothesis generation and testing on tabular datasets.
