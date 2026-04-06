# Open Questions

## reasonforge-skill-conversion - 2026-04-03 (v2 revision)

### Resolved

- [x] Should the runner's `mutate` callback be a true no-op placeholder? -- RESOLVED: The single-shot runner approach is invalidated. The `mutate` callback in `runReasonForgeCycle()` creates a new candidate that is immediately scored by `judge`. The Stateful CLI does not use `runReasonForgeCycle()` at all; mutation is handled by the Skill via Agent tool and registered via `cli.ts mutate`.
- [x] Should the runner support streaming events? -- RESOLVED: Not needed. The CLI returns JSON per subcommand call. The Skill can observe progress by calling `next-step` between operations.

### Still Open

- [ ] What is the preferred location for the Skill file: `.claude/commands/reasonforge.md` (project-level) or `~/.claude/commands/reasonforge.md` (user-level global)? -- Project-level makes it portable with the repo; global makes it available everywhere. Current plan assumes project-level.
- [ ] Should the Skill support a `--fast` mode that skips mutation/crossover and only does generate-then-critique (1 generation, no evolution)? -- Useful for quick answers where full evolution is overkill. Can be added later without architectural changes (just set generationLimit=0 in config).
- [ ] For the Mutator subagent, should it receive the full critique text or just the lowest-scoring dimension? -- Full critique is richer but may cause the LLM to over-correct on minor issues. Current plan sends full critique.
- [ ] Should the CLI be compiled to a standalone binary (via `pkg` or `esbuild`) or always invoked via `npx tsx`? -- `npx tsx` is simpler for development; a compiled binary is faster for production. Current plan assumes `npx tsx` for Phase 1.
