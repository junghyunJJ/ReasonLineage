#!/usr/bin/env node

import {
  handleInit,
  handleScore,
  handleSelect,
  handleMutate,
  handleCrossover,
  handleNextStep
} from "./handlers.js";

const COMMANDS: Record<string, (input: unknown) => unknown> = {
  init: handleInit as (input: unknown) => unknown,
  score: handleScore as (input: unknown) => unknown,
  select: handleSelect as (input: unknown) => unknown,
  mutate: handleMutate as (input: unknown) => unknown,
  crossover: handleCrossover as (input: unknown) => unknown,
  "next-step": handleNextStep as (input: unknown) => unknown
};

function main() {
  const [subcommand, jsonArg] = process.argv.slice(2);

  if (!subcommand || !(subcommand in COMMANDS)) {
    const available = Object.keys(COMMANDS).join(", ");
    console.error(JSON.stringify({ error: `Usage: cli.ts <${available}> '<json>'` }));
    process.exit(1);
  }

  let input: unknown;
  try {
    input = JSON.parse(jsonArg ?? "{}");
  } catch {
    console.error(JSON.stringify({ error: "Invalid JSON argument" }));
    process.exit(1);
  }

  try {
    const result = COMMANDS[subcommand](input);
    console.log(JSON.stringify(result, null, 2));
  } catch (err) {
    console.error(JSON.stringify({ error: err instanceof Error ? err.message : String(err) }));
    process.exit(1);
  }
}

main();
