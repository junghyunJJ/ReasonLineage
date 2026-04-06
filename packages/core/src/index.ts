export {
  evaluateBenchmarkAnswer,
  getDefaultBenchmarkCase,
  defaultBenchmarkMatcher
} from "./benchmark.js";
export type { BenchmarkMatcher } from "./benchmark.js";
export { calculateFitness, defaultJudgeWeights } from "./scoring.js";
export { createCandidate, runReasonForgeCycle } from "./engine.js";
export { DEFAULT_JUDGE_DIMENSIONS } from "./types.js";
export {
  CATEGORY_PRESETS,
  resolveWeights,
  classifyQuestion,
  getPresetWeights,
  getAllCategories
} from "./categories.js";
export type { QuestionCategory, CategoryPreset } from "./categories.js";
export type {
  BenchmarkCase,
  BenchmarkVerdict,
  Candidate,
  CandidateJudgeResult,
  DefaultJudgeDimension,
  EvolutionEvent,
  EvolutionStrategy,
  JudgeWeights,
  RunReasonForgeCycleInput,
  RunReasonForgeCycleResult,
  RunStatus,
  ScoredCandidate,
  SelectionStrategy,
  TerminationCondition
} from "./types.js";
