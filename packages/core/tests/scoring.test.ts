import { describe, expect, it } from "vitest";

import { calculateFitness, defaultJudgeWeights } from "../src/index";

describe("calculateFitness", () => {
  it("uses the approved weighted formula", () => {
    const fitness = calculateFitness(
      defaultJudgeWeights,
      {
        logicalConsistency: 0.9,
        evidenceGrounding: 0.5,
        solutionUsefulness: 0.8
      }
    );

    expect(fitness).toBeCloseTo(0.79, 5);
  });

  it("calculates fitness from dynamic scores with custom weights", () => {
    const scores = { accuracy: 0.9, creativity: 0.7, efficiency: 0.8, safety: 0.6 };
    const weights = { accuracy: 0.4, creativity: 0.2, efficiency: 0.3, safety: 0.1 };
    const result = calculateFitness(weights, scores);
    expect(result).toBeCloseTo(0.4 * 0.9 + 0.2 * 0.7 + 0.3 * 0.8 + 0.1 * 0.6);
  });

  it("works with purely custom dimensions (no defaults)", () => {
    const weights = { accuracy: 0.6, clarity: 0.4 };
    const scores = { accuracy: 0.8, clarity: 0.9 };
    const result = calculateFitness(weights, scores);
    expect(result).toBeCloseTo(0.6 * 0.8 + 0.4 * 0.9); // 0.84
  });

  it("normalizes weights that don't sum to 1.0", () => {
    const weights = { a: 2, b: 3 };
    const scores = { a: 1.0, b: 1.0 };
    const result = calculateFitness(weights, scores);
    expect(result).toBeCloseTo(1.0); // normalized: a=0.4, b=0.6, both score 1.0
  });

  it("returns 0 for missing score dimensions", () => {
    const weights = { accuracy: 0.5, clarity: 0.5 };
    const scores = { accuracy: 0.8 }; // clarity missing
    const result = calculateFitness(weights, scores);
    // normalized weights: accuracy=0.5, clarity=0.5
    // accuracy: 0.5 * 0.8 = 0.4, clarity: 0.5 * 0 = 0 -> total 0.4
    expect(result).toBeCloseTo(0.4);
  });

  it("returns 0 for empty weights", () => {
    const result = calculateFitness({}, { a: 0.5 });
    expect(result).toBe(0);
  });
});
