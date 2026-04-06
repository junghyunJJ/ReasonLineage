import type { JudgeWeights } from "./types.js";

export const defaultJudgeWeights: JudgeWeights = {
  logicalConsistency: 0.5,
  evidenceGrounding: 0.2,
  solutionUsefulness: 0.3
};

export function calculateFitness(
  weights: JudgeWeights,
  scores: Record<string, number>
): number {
  // Normalize weights to sum to 1.0
  const keys = Object.keys(weights).filter(k => weights[k] != null);
  const sum = keys.reduce((s, k) => s + (weights[k] ?? 0), 0);
  if (sum === 0) return 0;

  let total = 0;
  for (const key of keys) {
    const w = (weights[key] ?? 0) / sum;
    total += (scores[key] ?? 0) * w;
  }
  return total;
}
