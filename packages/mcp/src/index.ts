#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import {
  startSessionSchema,
  scoreCandidateSchema,
  selectSchema,
  mutateSchema,
  crossoverSchema,
  nextStepSchema
} from "./schemas.js";

import {
  handleStartSession,
  handleScoreCandidate,
  handleSelect,
  handleMutate,
  handleCrossover,
  handleNextStep
} from "./tools.js";

import { startSessionGC } from "./session.js";

const server = new McpServer({
  name: "reasonforge-evolution",
  version: "0.1.0"
});

// Register all 6 tools
server.registerTool(
  "reasonforge_start_session",
  {
    title: "Start Evolution Session",
    description:
      "Initialize a new evolutionary reasoning session. Provide seed candidate answers and optional configuration (threshold, weights, benchmark). Returns a session ID to use with other tools.",
    inputSchema: startSessionSchema
  },
  async (args) => handleStartSession(args)
);

server.registerTool(
  "reasonforge_score_candidate",
  {
    title: "Score Candidate",
    description:
      "Submit judge scores (0-1 per dimension) and critique for a candidate. The server calculates fitness automatically. Score each dimension from 0 to 1.",
    inputSchema: scoreCandidateSchema
  },
  async (args) => handleScoreCandidate(args)
);

server.registerTool(
  "reasonforge_select",
  {
    title: "Select Survivors",
    description:
      "Run selection on the current population. Keeps the top N candidates by fitness and advances to the next generation. All candidates must be scored first.",
    inputSchema: selectSchema
  },
  async (args) => handleSelect(args)
);

server.registerTool(
  "reasonforge_mutate",
  {
    title: "Submit Mutation",
    description:
      "Register a mutated candidate derived from a parent. You provide the improved answer text; the server tracks lineage. Score the new candidate after submitting.",
    inputSchema: mutateSchema
  },
  async (args) => handleMutate(args)
);

server.registerTool(
  "reasonforge_crossover",
  {
    title: "Submit Crossover",
    description:
      "Register a crossover candidate combining two parents. You provide the combined answer text; the server tracks lineage. Score the new candidate after submitting.",
    inputSchema: crossoverSchema
  },
  async (args) => handleCrossover(args)
);

server.registerTool(
  "reasonforge_next_step",
  {
    title: "Check Status & Get Guidance",
    description:
      "Call this tool FIRST to understand the current session state and get a suggested next action. Returns population status, best fitness, threshold check, and a structured suggestion with the recommended tool to call next.",
    inputSchema: nextStepSchema
  },
  async (args) => handleNextStep(args)
);

// Start server
async function main() {
  startSessionGC();
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("ReasonForge MCP Server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
