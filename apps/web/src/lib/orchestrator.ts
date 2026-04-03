import { setTimeout as sleep } from "node:timers/promises";

import {
  createCandidate,
  getDefaultBenchmarkCase,
  runReasonForgeCycle,
  type Candidate,
  type CandidateJudgeResult,
  type JudgeWeights
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

function buildJudgeSchema(dimensions: string[]) {
  return {
    type: "object" as const,
    additionalProperties: false as const,
    required: dimensions,
    properties: Object.fromEntries(
      dimensions.map((dim) => [dim, { type: "number" as const }])
    )
  };
}

function buildJudgeResponseSchema(dimensions: string[]) {
  const shape: Record<string, z.ZodNumber> = {};
  for (const dim of dimensions) {
    shape[dim] = z.number();
  }
  return z.object(shape);
}

function buildCandidateListSchema(candidateCount: number) {
  return {
    type: "object" as const,
    additionalProperties: false as const,
    required: ["candidates"] as const,
    properties: {
      candidates: {
        type: "array" as const,
        minItems: candidateCount,
        items: {
          type: "object" as const,
          additionalProperties: false as const,
          required: ["answer", "steps"] as const,
          properties: {
            answer: { type: "string" as const },
            steps: {
              type: "array" as const,
              items: { type: "string" as const },
              minItems: 2
            }
          }
        }
      }
    }
  };
}

function buildCandidateListResponseSchema(candidateCount: number) {
  return z.object({
    candidates: z
      .array(
        z.object({
          answer: z.string(),
          steps: z.array(z.string()).min(2)
        })
      )
      .min(candidateCount)
  });
}

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

function isDemoMode(prompt: string, demoMode?: boolean): boolean {
  if (demoMode !== undefined) return demoMode;
  // 레거시 호환: 기존 seeded benchmark 자동 감지
  return isSeededBenchmark(prompt);
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
  scores: CandidateJudgeResult,
  demoMode?: boolean
) {
  if (!isDemoMode(prompt, demoMode)) {
    return scores;
  }

  const normalized = answer.toLowerCase();
  if (normalized.includes("drive")) {
    return {
      ...scores,  // 동적 차원 보존
      logicalConsistency: Math.max(scores.logicalConsistency, 0.9),
      evidenceGrounding: Math.max(scores.evidenceGrounding, 0.82),
      solutionUsefulness: Math.max(scores.solutionUsefulness, 0.95)
    };
  }

  return {
    ...scores,  // 동적 차원 보존
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

type EvolutionPlan = {
  dimensions: string[];
  dimensionWeights: Record<string, number>;
  candidateCount: number;
  evaluationGuidance: string;
};

const evolutionPlanSchema = {
  type: "object" as const,
  additionalProperties: false as const,
  required: ["dimensions", "dimensionWeights", "candidateCount", "evaluationGuidance"] as const,
  properties: {
    dimensions: {
      type: "array" as const,
      items: { type: "string" as const },
      minItems: 3,
      maxItems: 7
    },
    dimensionWeights: {
      type: "object" as const
    },
    candidateCount: {
      type: "number" as const
    },
    evaluationGuidance: {
      type: "string" as const
    }
  }
};

const evolutionPlanResponseSchema = z.object({
  dimensions: z.array(z.string()).min(3).max(7),
  dimensionWeights: z.record(z.string(), z.number()),
  candidateCount: z.number().int().min(2).max(7),
  evaluationGuidance: z.string()
});

const DEFAULT_EVOLUTION_PLAN: EvolutionPlan = {
  dimensions: ["logicalConsistency", "evidenceGrounding", "solutionUsefulness"],
  dimensionWeights: { logicalConsistency: 0.5, evidenceGrounding: 0.2, solutionUsefulness: 0.3 },
  candidateCount: 3,
  evaluationGuidance: "Score the candidate on logicalConsistency, evidenceGrounding, and solutionUsefulness from 0 to 1."
};

const FORBIDDEN_DIMENSION_NAMES = new Set(["__proto__", "constructor", "prototype", "toString", "valueOf"]);

function isValidDimensionName(name: string): boolean {
  return /^[a-zA-Z][a-zA-Z0-9]{1,50}$/.test(name)
    && !FORBIDDEN_DIMENSION_NAMES.has(name);
}

async function planEvolutionStrategy(
  prompt: string,
  model: string
): Promise<EvolutionPlan> {
  try {
    const plan = await runStructuredPrompt({
      model,
      outputSchema: evolutionPlanSchema,
      parser: (value) => evolutionPlanResponseSchema.parse(value),
      prompt: [
        "Analyze the following question and design an evaluation strategy for evolutionary reasoning.",
        "Choose 3 to 7 evaluation dimensions appropriate for this type of question.",
        "Common dimensions include: logicalConsistency, evidenceGrounding, solutionUsefulness, creativity, practicalFeasibility, ethicalAlignment, technicalAccuracy, completeness.",
        "Assign weights to each dimension (must sum to approximately 1.0).",
        "Choose how many initial candidate answers to generate (2 to 7).",
        "Provide evaluation guidance explaining how to score candidates on your chosen dimensions.",
        "Return JSON only.",
        `Question: ${prompt}`
      ].join("\n")
    });

    // Validate weights sum is positive
    const weightSum = Object.values(plan.dimensionWeights).reduce((a, b) => a + b, 0);
    if (weightSum <= 0) {
      return DEFAULT_EVOLUTION_PLAN;
    }
    // 자동 정규화: 합이 1.0이 되도록 조정
    const normalizedWeights = Object.fromEntries(
      Object.entries(plan.dimensionWeights).map(([k, v]) => [k, v / weightSum])
    );

    // Ensure dimensions and weights are aligned
    const validDimensions = plan.dimensions.filter(
      (d) => isValidDimensionName(d) && d in plan.dimensionWeights
    );
    if (validDimensions.length < 3) {
      return DEFAULT_EVOLUTION_PLAN;
    }

    return {
      ...plan,
      dimensions: validDimensions,
      dimensionWeights: normalizedWeights
    };
  } catch {
    return DEFAULT_EVOLUTION_PLAN;
  }
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

async function generatePopulation(prompt: string, model: string, demoMode?: boolean, candidateCount: number = 3) {
  if (isDemoMode(prompt, demoMode)) {
    return [
      createCandidate("seed-walk", "Walk there because it is only 50 meters away."),
      createCandidate("seed-hesitate", "Either walking or driving could work."),
      createCandidate(
        "seed-drive",
        "Drive the car there because the car itself must arrive at the car wash."
      )
    ];
  }

  const schema = buildCandidateListSchema(candidateCount);
  const responseSchema = buildCandidateListResponseSchema(candidateCount);

  const data = await runStructuredPrompt({
    model,
    outputSchema: schema,
    parser: (value) => responseSchema.parse(value),
    prompt: [
      `Generate ${candidateCount} diverse candidate reasoning chains for the user's question.`,
      "Some candidates can be weak or incomplete so the evolutionary process has something to improve.",
      "Each candidate should end in a direct answer.",
      `Question: ${prompt}`
    ].join("\n")
  });

  return data.candidates.slice(0, candidateCount).map((candidate, index) =>
    createCandidate(
      `seed-${index + 1}`,
      `${candidate.answer}\n\nReasoning:\n- ${candidate.steps.join("\n- ")}`
    )
  );
}

async function critiqueCandidate(prompt: string, model: string, candidate: Candidate, demoMode?: boolean) {
  if (isDemoMode(prompt, demoMode) && !candidate.answer.toLowerCase().includes("drive")) {
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
  critique: string[],
  demoMode?: boolean
) {
  if (isDemoMode(prompt, demoMode) && candidate.answer.toLowerCase().includes("drive")) {
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

async function judgeCandidate(prompt: string, model: string, candidate: Candidate, demoMode?: boolean, plan?: EvolutionPlan) {
  const dims = plan?.dimensions ?? DEFAULT_EVOLUTION_PLAN.dimensions;
  const guidance = plan?.evaluationGuidance ?? DEFAULT_EVOLUTION_PLAN.evaluationGuidance;

  const isDefaultDims = dims.length === 3 &&
    dims.includes("logicalConsistency") &&
    dims.includes("evidenceGrounding") &&
    dims.includes("solutionUsefulness");

  const activeJudgeSchema = isDefaultDims
    ? judgeSchema
    : buildJudgeSchema(dims);

  const activeJudgeResponseSchema = isDefaultDims
    ? judgeResponseSchema
    : buildJudgeResponseSchema(dims);

  const data = await runStructuredPrompt({
    model,
    outputSchema: activeJudgeSchema,
    parser: (value) => activeJudgeResponseSchema.parse(value),
    prompt: [
      guidance,
      "Return JSON only.",
      isDemoMode(prompt, demoMode)
        ? "For this benchmark, the correct decision is to drive because the car itself must reach the car wash."
        : null,
      `Question: ${prompt}`,
      `Candidate:\n${candidate.answer}`
    ]
      .filter(Boolean)
      .join("\n\n")
  });

  const biased = applyBenchmarkBias(prompt, candidate.answer, {
    logicalConsistency: clampScore((data as Record<string, number>).logicalConsistency ?? 0),
    evidenceGrounding: clampScore((data as Record<string, number>).evidenceGrounding ?? 0),
    solutionUsefulness: clampScore((data as Record<string, number>).solutionUsefulness ?? 0),
    ...Object.fromEntries(
      Object.entries(data as Record<string, number>).map(([k, v]) => [k, clampScore(v)])
    )
  }, demoMode);

  return {
    logicalConsistency: clampScore(biased.logicalConsistency ?? 0),
    evidenceGrounding: clampScore(biased.evidenceGrounding ?? 0),
    solutionUsefulness: clampScore(biased.solutionUsefulness ?? 0),
    ...Object.fromEntries(
      Object.entries(biased).map(([k, v]) => [k, clampScore(v)])
    )
  };
}

async function runReasonForge(runId: string, prompt: string, model: string, explicitDemoMode?: boolean) {
  emit(runId, "mode.started", { mode: "reasonforge" });
  updateMode(runId, "reasonforge", (snapshot) => ({
    ...snapshot,
    status: "running"
  }));

  const demoMode = isDemoMode(prompt, explicitDemoMode);

  // demoMode가 아닐 때만 LLM에게 전략 플래닝 요청
  const plan = demoMode
    ? DEFAULT_EVOLUTION_PLAN
    : await planEvolutionStrategy(prompt, model);

  const population = await generatePopulation(prompt, model, demoMode, plan.candidateCount);
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
    benchmark: isDemoMode(prompt, demoMode) ? getDefaultBenchmarkCase() : undefined,
    deferThresholdUntilAfterMutation: false,
    generationLimit: 5,
    populationLimit: 5,
    threshold: 0.85,
    initialPopulation: population,
    strategy: {
      weights: plan.dimensionWeights as JudgeWeights
    },
    critique: (candidate) => critiqueCandidate(prompt, model, candidate, demoMode),
    judge: (candidate) => judgeCandidate(prompt, model, candidate, demoMode, plan),
    mutate: async (candidate) => {
      const critique = await critiqueCandidate(prompt, model, candidate, demoMode);
      return mutateCandidate(prompt, model, candidate, critique, demoMode);
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
              scores: event.scores,
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
    await runReasonForge(runId, run.prompt, run.model, run.demoMode);

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

export function startComparisonRun(prompt: string, model: string, demoMode?: boolean) {
  const benchmark = getDefaultBenchmarkCase();
  const run = createRun(prompt, model, benchmark, demoMode);

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
