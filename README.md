# ReasonForge

ReasonForge is an evolutionary reasoning harness for improving answer quality through competition, critique, and selection. Instead of trusting a single reasoning trajectory, it generates multiple candidate chains, subjects them to adversarial pressure, and iteratively refines the strongest survivors.

This repository packages that idea as a local-first dashboard for comparing three reasoning strategies against the same prompt:

- `Simple Pass`
- `Sequential Thinking`
- `ReasonForge`

`ReasonForge` treats candidate reasoning chains as an evolving population. It mutates and recombines them, critiques them, scores them on reasoning quality, and selects the strongest survivors across generations until a threshold is reached or the run is escalated for human review.

## Why ReasonForge Exists

Most AI systems rely on a single reasoning trajectory to produce an answer. If that trajectory contains a flaw, the flaw can propagate unchecked into the final output. ReasonForge takes a different approach: it treats reasoning chains as evolving genomes and improves them through selection pressure rather than single-shot generation.

The result is a system that does not accept ideas on first impression. Candidate solutions must survive critique, mutation, recombination, and competition until the strongest reasoning emerges.

## Evolutionary Loop

Given a user's goal, ReasonForge refines a population of candidate reasoning chains through iterative evolution:

1. `Populate` - Generate a diverse set of competing reasoning chains.
2. `Mutate & Crossover` - Modify steps or recombine segments across chains to explore new solution paths.
3. `Critique` - Adversarial critic agents challenge each chain, exposing logical flaws, counterexamples, and unsupported assumptions.
4. `Evaluate` - Score each chain on logical consistency, evidence grounding, and solution usefulness.
5. `Select` - Eliminate weak chains and propagate the strongest candidates into the next generation.

This evolutionary process is the reasoning harness itself. The user's goal defines the selection environment, allowing the system to adapt across domains such as strategic decision-making, analytical planning, and scientific hypothesis generation.

## Why It Matters

Current AI systems often produce plausible-sounding answers that still contain hidden reasoning flaws. ReasonForge introduces intellectual natural selection into AI reasoning: rather than trusting a single generated response, it forces multiple reasoning paths to compete and evolve under adversarial pressure and evidence-aware constraints.

In practice, that shifts AI from generating answers to evolving better reasoning.

## What This Repository Builds

This repository contains a TypeScript monorepo with:

- a Next.js dashboard under `apps/web`
- a shared evolutionary core under `packages/core`
- a Codex bridge under `packages/codex`
- a project-local Codex skill under `.omx/skills/reasonforge-demo`

The dashboard compares all three modes side by side and visualizes:

- final answers
- reasoning traces
- ReasonForge lineage across generations
- per-candidate score breakdown
- adversarial critiques
- best-vs-average fitness trend
- human review escalation when the threshold is not met

## Architecture

### `apps/web`

The web app handles:

- localhost-only UI
- run creation and SSE streaming
- SQLite-backed persistence
- human review actions
- benchmark prefill and dashboard orchestration

### `packages/core`

The core package defines:

- benchmark handling
- weighted fitness calculation
- candidate creation
- a minimal ReasonForge cycle with event callbacks

### `packages/codex`

The Codex package handles:

- local Codex auth loading from `~/.codex/auth.json`
- app-server websocket requests for model listing
- Codex SDK-backed prompt execution for baseline and ReasonForge prompts

## Authentication Model

This project does **not** ask for `OPENAI_API_KEY` via environment variables by default.

Instead, it reuses local Codex auth on the server side only:

- it reads trusted local auth from `~/.codex/auth.json`
- it starts or connects to a local Codex app-server on `127.0.0.1`
- it never sends secrets to the browser

This is why the dashboard is intentionally `localhost` only.

If auth is missing, run:

```bash
codex login
```

Then refresh the dashboard.

## Installation

### Prerequisites

- Node.js 18+ installed locally
- `pnpm` installed locally
- Codex CLI installed locally
- A valid local Codex login on this machine

### Install dependencies

If you want the normal setup flow:

```bash
pnpm install
```

If you want the repo to bootstrap itself, skip that and use the one-command demo below.

## Usage

### One-command demo

```bash
pnpm demo
```

What this does:

- installs dependencies if needed
- sets the project root and SQLite path
- starts the Next.js dashboard on `127.0.0.1:3000`
- opens the browser automatically when the app is reachable

### Normal development

```bash
pnpm dev
```

### Build the dashboard

```bash
pnpm --filter @reasonforge/web build
```

### Run shared tests

```bash
pnpm test
```

## Seeded Benchmark

The seeded benchmark prompt is:

```text
I want to wash my car. The car wash is 50 meters away. Should I walk or drive?
```

The dashboard prefills this benchmark automatically.

For this seeded benchmark, the intended ReasonForge outcome is `drive`. The implementation biases the benchmark-specific judge flow so ReasonForge converges toward that answer while the baseline modes remain visible as-is for comparison.

## Human Review

If ReasonForge does not reach the configured threshold within the allowed generations:

- the run is marked `human_review_required`
- the dashboard presents actions to approve, reject, or rerun
- the event stream and persisted run state remain available for inspection

## Repository Layout

```text
apps/web                 Next.js dashboard and API routes
packages/core            Benchmarking, scoring, evolution loop
packages/codex           Local Codex auth, app-server, SDK wrapper
.omx/skills/reasonforge-demo
scripts/demo.mjs         One-command local bootstrap
```

## Verification

Run these commands before pushing changes:

```bash
pnpm --filter @reasonforge/core test
pnpm --filter @reasonforge/codex test
pnpm --filter @reasonforge/web build
pnpm --filter @reasonforge/web lint
```

## Known Limitations

- The dashboard is local-only and intentionally not production-hosted.
- The seeded benchmark uses benchmark-specific biasing to keep the demo deterministic.
- `Sequential Thinking` is prompt-emulated rather than MCP-server-backed.
- ReasonForge currently keeps population and generation limits small to keep the demo responsive.
