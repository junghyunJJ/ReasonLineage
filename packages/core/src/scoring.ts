import type { CandidateJudgeResult, JudgeWeights } from "./types";

export const defaultJudgeWeights: JudgeWeights = {
  logicalConsistency: 0.5,
  evidenceGrounding: 0.2,
  solutionUsefulness: 0.3
};

export function calculateFitness(
  scores: CandidateJudgeResult,
  weights: JudgeWeights = defaultJudgeWeights
) {
  return (
    scores.logicalConsistency * weights.logicalConsistency +
    scores.evidenceGrounding * weights.evidenceGrounding +
    scores.solutionUsefulness * weights.solutionUsefulness
  );
}
