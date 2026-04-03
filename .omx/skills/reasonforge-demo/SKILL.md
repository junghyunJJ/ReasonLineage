---
name: reasonforge-demo
description: Use when you need to launch the local ReasonForge dashboard, rerun the seeded car-wash benchmark, or inspect why ReasonForge failed to converge to drive in this repository.
---

# ReasonForge Demo

Use this skill only inside this repository.

## Quick start

- Run `pnpm demo`
- Wait for the dashboard to open on `http://127.0.0.1:3000`
- The seeded benchmark prompt is already filled in
- Click `Run Comparison`

## What good looks like

- The model picker is populated from local Codex
- `Simple Pass`, `Sequential Thinking`, and `ReasonForge` all run against the same prompt
- ReasonForge streams lineage, critiques, and fitness updates live
- For the seeded benchmark, ReasonForge should converge to `drive`

## Verification

- `pnpm --filter @reasonforge/core test`
- `pnpm --filter @reasonforge/codex test`
- `pnpm --filter @reasonforge/web build`

## Gotchas

- This repo reuses local Codex auth from `~/.codex/auth.json`
- The dashboard is intentionally localhost-only
- If auth is missing, run `codex login` and refresh
