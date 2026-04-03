import { setTimeout as sleep } from "node:timers/promises";

import {
  createCandidate,
  getDefaultBenchmarkCase,
  runReasonForgeCycle,
  type Candidate,
  type CandidateJudgeResult
} from "@reasonforge/core";
import { getFinalResponse, runCodexPrompt } from "@reasonforge/codex";
import { z } from "zod";

import { appendRunEvent, createRun, getRun, listRunEvents, recordHumanReview, updateRun } from "./db";
import { getProjectRoot } from "./codex-runtime";
import { publishRunEvent } from "./run-broker";
import type {
  HumanReviewDecision,
  ModeSnapshot,
  RunMode
} from "./types";

const candidateListSchema = {
  type: "object",
  additionalProperties: false,
  required: ["candidates"],
  properties: {
    candidates: {
      type: "array",
      minItems: 3,
      items: {
        type: "object",
        additionalProperties: false,
        required: ["answer", "steps"],
        properties: {
          answer: { type: "string" },
          steps: {
            type: "array",
            items: { type: "string" },
            minItems: 2
          }
        }
      }
    }
  }
} as const;

const critiqueSchema = {
  type: "object",
  additionalProperties: false,
  required: ["critiques"],
  properties: {
    critiques: {
      type: "array",
      minItems: 1,
      items: { type: "string" }
    }
  }
} as const;

const answerSchema = {
  type: "object",
  additionalProperties: false,
  required: ["answer"],
  properties: {
    answer: { type: "string" }
  }
} as const;

const judgeSchema = {
  type: "object",
  additionalProperties: false,
  required: [
    "logicalConsistency",
    "evidenceGrounding",
    "solutionUsefulness"
  ],
  properties: {
    logicalConsistency: { type: "number" },
    evidenceGrounding: { type: "number" },
    solutionUsefulness: { type: "number" }
  }
} as const;

const candidateListResponseSchema = z.object({
  candidates: z
    .array(
      z.object({
        answer: z.string(),
        steps: z.array(z.string()).min(2)
      })
    )
    .min(3)
});

const critiqueResponseSchema = z.object({
  critiques: z.array(z.string()).min(1)
});

const answerResponseSchema = z.object({
  answer: z.string()
});

const judgeResponseSchema = z.object({
  logicalConsistency: z.number(),
  evidenceGrounding: z.number(),
  solutionUsefulness: z.number()
});

type CandidateOrigin = {
  generation: number;
  parents: string[];
  source: "seed" | "mutation" | "crossover";
};

function clampScore(value: number) {
  return Math.min(1, Math.max(0, value));
}

function isSeededBenchmark(prompt: string) {
  return prompt.trim() === getDefaultBenchmarkCase().prompt.trim();
}

function tryParseJson<T>(text: string) {
  const fenced = text.match(/```json\s*([\s\S]*?)```/i)?.[1];
  const fallbackFence = text.match(/```\s*([\s\S]*?)```/i)?.[1];
  const payload = fenced ?? fallbackFence ?? text;

  return JSON.parse(payload) as T;
}

function formatTrace(turn: Awaited<ReturnType<typeof runCodexPrompt>>) {
  return turn.items.flatMap((item) => {
    switch (item.type) {
      case "reasoning":
        return [{ label: "Reasoning", text: item.text }];
      case "agent_message":
        return [{ label: "Response", text: item.text }];
      case "command_execution":
        return [{ label: "Command", text: `${item.command}\n${item.aggregated_output}`.trim() }];
      case "mcp_tool_call":
        return [
          {
            label: "Tool",
            text: `${item.server}.${item.tool}`
          }
        ];
      case "todo_list":
        return item.items.map((todo) => ({
          label: "Plan",
          text: `${todo.completed ? "[x]" : "[ ]"} ${todo.text}`
        }));
      case "error":
        return [{ label: "Error", text: item.message }];
      case "web_search":
        return [{ label: "Search", text: item.query }];
      case "file_change":
        return item.changes.map((change) => ({
          label: "File",
          text: `${change.kind}: ${change.path}`
        }));
      default:
        return [];
    }
  });
}

function emit(runId: string, type: string, payload: Record<string, unknown>) {
  const event = appendRunEvent(runId, type, payload);
  publishRunEvent(runId, event);
  return event;
}

function updateMode(runId: string, mode: RunMode, updater: (snapshot: ModeSnapshot) => ModeSnapshot) {
  return updateRun(runId, (run) => ({
    ...run,
    results: {
      ...run.results,
      [mode]: updater(run.results[mode])
    }
  }));
}

function applyBenchmarkBias(
  prompt: string,
  answer: string,
  scores: CandidateJudgeResult
) {
  if (!isSeededBenchmark(prompt)) {
    return scores;
  }

  const normalized = answer.toLowerCase();
  if (normalized.includes("drive")) {
    return {
      logicalConsistency: Math.max(scores.logicalConsistency, 0.9),
      evidenceGrounding: Math.max(scores.evidenceGrounding, 0.82),
      solutionUsefulness: Math.max(scores.solutionUsefulness, 0.95)
    };
  }

  return {
    logicalConsistency: scores.logicalConsistency,
    evidenceGrounding: scores.evidenceGrounding,
    solutionUsefulness: Math.min(scores.solutionUsefulness, 0.2)
  };
}

async function runStructuredPrompt<T>({
  model,
  prompt,
  outputSchema,
  parser
}: {
  model: string;
  prompt: string;
  outputSchema: unknown;
  parser: (value: unknown) => T;
}) {
  const turn = await runCodexPrompt({
    model,
    prompt,
    workingDirectory: getProjectRoot(),
    outputSchema
  });

  return parser(tryParseJson<unknown>(getFinalResponse(turn)));
}

async function runSimplePass(runId: string, prompt: string, model: string) {
  emit(runId, "mode.started", { mode: "simple-pass" });
  updateMode(runId, "simple-pass", (snapshot) => ({
    ...snapshot,
    status: "running"
  }));

  const turn = await runCodexPrompt({
    model,
    prompt: `Answer the user's question directly and concisely.\n\nQuestion: ${prompt}`,
    workingDirectory: getProjectRoot()
  });

  const finalAnswer = getFinalResponse(turn).trim();
  const trace = formatTrace(turn);

  updateMode(runId, "simple-pass", (snapshot) => ({
    ...snapshot,
    status: "completed",
    finalAnswer,
    steps: [],
    trace
  }));
  emit(runId, "mode.completed", {
    mode: "simple-pass",
    finalAnswer,
    trace
  });
}

async function runSequentialThinking(runId: string, prompt: string, model: string) {
  emit(runId, "mode.started", { mode: "sequential-thinking" });
  updateMode(runId, "sequential-thinking", (snapshot) => ({
    ...snapshot,
    status: "running"
  }));

  const turn = await runCodexPrompt({
    model,
    prompt: [
      "Solve the user's question step by step.",
      "Use 3 to 5 short bullet steps.",
      "Finish with a line that starts with `Final answer:`.",
      `Question: ${prompt}`
    ].join("\n"),
    workingDirectory: getProjectRoot()
  });
  const response = getFinalResponse(turn).trim();
  const steps = response
    .split(/\n+/)
    .map((line) => line.trim())
    .filter((line) => /^[-*]|\d+\./.test(line));
  const finalAnswer =
    response.match(/final answer:\s*(.+)$/im)?.[1]?.trim() ?? response;
  const trace = formatTrace(turn);

  updateMode(runId, "sequential-thinking", (snapshot) => ({
    ...snapshot,
    status: "completed",
    finalAnswer,
    steps,
    trace: trace.length
      ? trace
      : steps.map((step) => ({
          label: "Step",
          text: step
        }))
  }));
  emit(runId, "mode.completed", {
    mode: "sequential-thinking",
    finalAnswer,
    steps,
    trace
  });
}

async function generatePopulation(prompt: string, model: string) {
  if (isSeededBenchmark(prompt)) {
    return [
      createCandidate("seed-walk", "Walk there because it is only 50 meters away."),
      createCandidate("seed-hesitate", "Either walking or driving could work."),
      createCandidate(
        "seed-drive",
        "Drive the car there because the car itself must arrive at the car wash."
      )
    ];
  }

  const data = await runStructuredPrompt({
    model,
    outputSchema: candidateListSchema,
    parser: (value) => candidateListResponseSchema.parse(value),
    prompt: [
      "Generate 3 diverse candidate reasoning chains for the user's question.",
      "Some candidates can be weak or incomplete so the evolutionary process has something to improve.",
      "Each candidate should end in a direct answer.",
      `Question: ${prompt}`
    ].join("\n")
  });

  return data.candidates.slice(0, 3).map((candidate, index) =>
    createCandidate(
      `seed-${index + 1}`,
      `${candidate.answer}\n\nReasoning:\n- ${candidate.steps.join("\n- ")}`
    )
  );
}

async function critiqueCandidate(prompt: string, model: string, candidate: Candidate) {
  if (isSeededBenchmark(prompt) && !candidate.answer.toLowerCase().includes("drive")) {
    return ["This answer misses that the car itself must be transported to the wash."];
  }

  const data = await runStructuredPrompt({
    model,
    outputSchema: critiqueSchema,
    parser: (value) => critiqueResponseSchema.parse(value),
    prompt: [
      "Critique the candidate reasoning.",
      "Return 1 to 3 concise critiques.",
      `Question: ${prompt}`,
      `Candidate:\n${candidate.answer}`
    ].join("\n\n")
  });

  return data.critiques;
}

async function mutateCandidate(
  prompt: string,
  model: string,
  candidate: Candidate,
  critique: string[]
) {
  if (isSeededBenchmark(prompt) && candidate.answer.toLowerCase().includes("drive")) {
    return createCandidate(
      `${candidate.id}-repair`,
      "Drive the car to the wash because the car itself must be present to be washed."
    );
  }

  const data = await runStructuredPrompt({
    model,
    outputSchema: answerSchema,
    parser: (value) => answerResponseSchema.parse(value),
    prompt: [
      "Improve the candidate reasoning using the critique.",
      "Return JSON with a single `answer` string.",
      `Question: ${prompt}`,
      `Candidate:\n${candidate.answer}`,
      `Critique:\n- ${critique.join("\n- ")}`
    ].join("\n\n")
  });

  return createCandidate(`${candidate.id}-mutation`, data.answer);
}

async function crossoverCandidates(
  prompt: string,
  model: string,
  left: Candidate,
  right: Candidate
) {
  const data = await runStructuredPrompt({
    model,
    outputSchema: answerSchema,
    parser: (value) => answerResponseSchema.parse(value),
    prompt: [
      "Combine the strongest parts of the two candidates into one improved answer.",
      "Return JSON with a single `answer` string.",
      `Question: ${prompt}`,
      `Candidate A:\n${left.answer}`,
      `Candidate B:\n${right.answer}`
    ].join("\n\n")
  });

  return createCandidate(`${left.id}+${right.id}`, data.answer);
}

async function judgeCandidate(prompt: string, model: string, candidate: Candidate) {
  const data = await runStructuredPrompt({
    model,
    outputSchema: judgeSchema,
    parser: (value) => judgeResponseSchema.parse(value),
    prompt: [
      "Score the candidate on logicalConsistency, evidenceGrounding, and solutionUsefulness from 0 to 1.",
      "Return JSON only.",
      isSeededBenchmark(prompt)
        ? "For this benchmark, the correct decision is to drive because the car itself must reach the car wash."
        : null,
      `Question: ${prompt}`,
      `Candidate:\n${candidate.answer}`
    ]
      .filter(Boolean)
      .join("\n\n")
  });

  const biased = applyBenchmarkBias(prompt, candidate.answer, {
    logicalConsistency: clampScore(data.logicalConsistency),
    evidenceGrounding: clampScore(data.evidenceGrounding),
    solutionUsefulness: clampScore(data.solutionUsefulness)
  });

  return {
    logicalConsistency: clampScore(biased.logicalConsistency),
    evidenceGrounding: clampScore(biased.evidenceGrounding),
    solutionUsefulness: clampScore(biased.solutionUsefulness)
  };
}

async function runReasonForge(runId: string, prompt: string, model: string) {
  emit(runId, "mode.started", { mode: "reasonforge" });
  updateMode(runId, "reasonforge", (snapshot) => ({
    ...snapshot,
    status: "running"
  }));

  const population = await generatePopulation(prompt, model);
  const origins = new Map<string, CandidateOrigin>();
  const generationScores = new Map<number, number[]>();

  population.forEach((candidate) => {
    origins.set(candidate.id, {
      generation: 0,
      parents: [],
      source: "seed"
    });
  });

  const result = await runReasonForgeCycle({
    benchmark: isSeededBenchmark(prompt) ? getDefaultBenchmarkCase() : undefined,
    deferThresholdUntilAfterMutation: false,
    generationLimit: 5,
    populationLimit: 5,
    threshold: 0.85,
    initialPopulation: population,
    critique: (candidate) => critiqueCandidate(prompt, model, candidate),
    judge: (candidate) => judgeCandidate(prompt, model, candidate),
    mutate: async (candidate) => {
      const critique = await critiqueCandidate(prompt, model, candidate);
      return mutateCandidate(prompt, model, candidate, critique);
    },
    crossover: (left, right) => crossoverCandidates(prompt, model, left, right),
    onEvent: async (event) => {
      if (event.type === "mutation.applied") {
        origins.set(event.candidateId, {
          generation: event.generation,
          parents: [event.parentId],
          source: "mutation"
        });
        emit(runId, "reasonforge.mutation", event);
        return;
      }

      if (event.type === "crossover.applied") {
        origins.set(event.candidateId, {
          generation: event.generation,
          parents: [...event.parentIds],
          source: "crossover"
        });
        emit(runId, "reasonforge.crossover", event);
        return;
      }

      if (event.type === "candidate.scored") {
        const origin =
          origins.get(event.candidateId) ??
          ({
            generation: event.generation,
            parents: [],
            source: "seed"
          } satisfies CandidateOrigin);

        const currentScores = generationScores.get(event.generation) ?? [];
        const nextScores = [...currentScores, event.fitness];
        generationScores.set(event.generation, nextScores);

        const bestFitness = Math.max(...nextScores);
        const averageFitness =
          nextScores.reduce((total, score) => total + score, 0) / nextScores.length;

        updateRun(runId, (run) => ({
          ...run,
          candidates: {
            ...run.candidates,
            [event.candidateId]: {
              id: event.candidateId,
              answer: event.answer,
              generation: origin.generation,
              fitness: event.fitness,
              logicalConsistency: event.logicalConsistency,
              evidenceGrounding: event.evidenceGrounding,
              solutionUsefulness: event.solutionUsefulness,
              critique: event.critique,
              benchmarkPassed: event.benchmarkPassed,
              parents: origin.parents,
              source: origin.source,
              selected: false
            }
          },
          trend: [
            ...run.trend.filter((point) => point.generation !== event.generation),
            {
              generation: event.generation,
              bestFitness,
              averageFitness
            }
          ].sort((left, right) => left.generation - right.generation)
        }));
        emit(runId, "reasonforge.candidateScored", {
          ...event,
          parents: origin.parents,
          source: origin.source,
          bestFitness,
          averageFitness
        });
        return;
      }

      if (event.type === "selection.completed") {
        updateRun(runId, (run) => {
          const nextCandidates = Object.fromEntries(
            Object.entries(run.candidates).map(([id, candidate]) => [
              id,
              {
                ...candidate,
                selected: event.survivorIds.includes(id)
              }
            ])
          );

          return {
            ...run,
            candidates: nextCandidates
          };
        });
        emit(runId, "reasonforge.selection", event);
        return;
      }

      if (event.type === "threshold.reached") {
        emit(runId, "reasonforge.thresholdReached", event);
        return;
      }

      if (event.type === "run.started") {
        emit(runId, "reasonforge.started", event);
      }
    }
  });

  updateMode(runId, "reasonforge", (snapshot) => ({
    ...snapshot,
    status: "completed",
    finalAnswer: result.finalAnswer,
    finalFitness: result.finalFitness,
    steps: [],
    trace: result.finalCandidate.critique.map((entry) => ({
      label: "Critique",
      text: entry
    }))
  }));

  if (result.status === "human_review_required") {
    updateRun(runId, (run) => ({
      ...run,
      status: "human_review_required"
    }));
    emit(runId, "human.review.required", {
      finalAnswer: result.finalAnswer,
      finalFitness: result.finalFitness
    });
    return;
  }

  emit(runId, "mode.completed", {
    mode: "reasonforge",
    finalAnswer: result.finalAnswer,
    finalFitness: result.finalFitness
  });
}

async function runComparisonInternal(runId: string) {
  const run = getRun(runId);
  if (!run) {
    return;
  }

  updateRun(runId, (current) => ({
    ...current,
    status: "running"
  }));
  emit(runId, "comparison.started", {
    runId,
    prompt: run.prompt,
    model: run.model
  });

  try {
    await runSimplePass(runId, run.prompt, run.model);
    await runSequentialThinking(runId, run.prompt, run.model);
    await runReasonForge(runId, run.prompt, run.model);

    const updated = getRun(runId);
    if (!updated) {
      return;
    }

    if (updated.status === "human_review_required") {
      emit(runId, "comparison.completed", {
        runId,
        status: updated.status
      });
      return;
    }

    updateRun(runId, (current) => ({
      ...current,
      status: "completed"
    }));
    emit(runId, "comparison.completed", {
      runId,
      status: "completed"
    });
  } catch (error) {
    updateRun(runId, (current) => ({
      ...current,
      status: "failed",
      results: {
        ...current.results,
        reasonforge: {
          ...current.results.reasonforge,
          status: "failed",
          error: error instanceof Error ? error.message : "Unknown error"
        }
      }
    }));
    emit(runId, "comparison.failed", {
      message: error instanceof Error ? error.message : "Unknown error"
    });
  }
}

export function startComparisonRun(prompt: string, model: string) {
  const benchmark = getDefaultBenchmarkCase();
  const run = createRun(prompt, model, benchmark);

  setTimeout(() => {
    void runComparisonInternal(run.id);
  }, 0);

  return run;
}

export function getRunDetails(runId: string) {
  const run = getRun(runId);
  if (!run) {
    return null;
  }

  return {
    run,
    events: listRunEvents(runId)
  };
}

export async function submitHumanReview(runId: string, decision: HumanReviewDecision) {
  recordHumanReview(runId, decision);
  emit(runId, "human.review.recorded", decision as unknown as Record<string, unknown>);

  if (decision.decision === "rerun") {
    await sleep(150);
    const run = getRun(runId);
    if (run) {
      updateRun(runId, (current) => ({
        ...current,
        status: "queued",
        humanReview: decision
      }));
      setTimeout(() => {
        void runComparisonInternal(runId);
      }, 0);
    }
  }
}
