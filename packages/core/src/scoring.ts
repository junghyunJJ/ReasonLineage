import type { CandidateJudgeResult, JudgeWeights } from "./types.js";

export const defaultJudgeWeights: JudgeWeights = {
  logicalConsistency: 0.5,
  evidenceGrounding: 0.2,
  solutionUsefulness: 0.3
};

export function calculateFitness(
  scores: CandidateJudgeResult,
  weights: JudgeWeights = defaultJudgeWeights,
  dynamicScores?: Record<string, number>
) {
  if (dynamicScores && Object.keys(dynamicScores).length > 0) {
    return Object.keys(weights).reduce(
      (sum, key) => sum + (dynamicScores[key] ?? 0) * weights[key],
      0
    );
  }
  return (
    scores.logicalConsistency * weights.logicalConsistency +
    scores.evidenceGrounding * weights.evidenceGrounding +
    scores.solutionUsefulness * weights.solutionUsefulness
  );
}
