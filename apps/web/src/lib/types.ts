import type { BenchmarkCase } from "@reasonforge/core";

export type RunMode = "simple-pass" | "sequential-thinking" | "reasonforge";
export type ModeStatus = "pending" | "running" | "completed" | "failed";
export type RunStatus =
  | "queued"
  | "running"
  | "completed"
  | "human_review_required"
  | "failed";

export type TraceEntry = {
  label: string;
  text: string;
};

export type ModeSnapshot = {
  mode: RunMode;
  title: string;
  status: ModeStatus;
  finalAnswer?: string;
  finalFitness?: number;
  steps: string[];
  trace: TraceEntry[];
  error?: string;
};

export type CandidateCard = {
  id: string;
  answer: string;
  generation: number;
  fitness: number;
  logicalConsistency: number;
  evidenceGrounding: number;
  solutionUsefulness: number;
  scores?: Record<string, number>;
  critique: string[];
  benchmarkPassed: boolean;
  parents: string[];
  source: "seed" | "mutation" | "crossover";
  selected: boolean;
};

export type TrendPoint = {
  generation: number;
  bestFitness: number;
  averageFitness: number;
};

export type HumanReviewDecision = {
  decision: "approve" | "reject" | "rerun";
  notes?: string;
  createdAt: string;
};

export type PublicRunEvent = {
  sequence: number;
  type: string;
  payload: Record<string, unknown>;
  createdAt: string;
};

export type RunRecord = {
  id: string;
  prompt: string;
  benchmark: BenchmarkCase;
  model: string;
  status: RunStatus;
  demoMode?: boolean;
  results: Record<RunMode, ModeSnapshot>;
  candidates: Record<string, CandidateCard>;
  trend: TrendPoint[];
  humanReview: HumanReviewDecision | null;
  createdAt: string;
  updatedAt: string;
};

export type BootstrapData = {
  benchmark: BenchmarkCase;
  prefillPrompt: string;
  models: Array<{
    id: string;
    displayName: string;
    isDefault: boolean;
  }>;
  authReady: boolean;
  authMessage: string | null;
};

export function createEmptyMode(mode: RunMode, title: string): ModeSnapshot {
  return {
    mode,
    title,
    status: "pending",
    steps: [],
    trace: []
  };
}

export function createInitialRunRecord(args: {
  id: string;
  prompt: string;
  benchmark: BenchmarkCase;
  model: string;
  createdAt: string;
  demoMode?: boolean;
}): RunRecord {
  return {
    id: args.id,
    prompt: args.prompt,
    benchmark: args.benchmark,
    model: args.model,
    status: "queued",
    demoMode: args.demoMode,
    results: {
      "simple-pass": createEmptyMode("simple-pass", "Simple Pass"),
      "sequential-thinking": createEmptyMode(
        "sequential-thinking",
        "Sequential Thinking"
      ),
      reasonforge: createEmptyMode("reasonforge", "ReasonForge")
    },
    candidates: {},
    trend: [],
    humanReview: null,
    createdAt: args.createdAt,
    updatedAt: args.createdAt
  };
}
