import { describe, expect, it } from "vitest";

import { calculateFitness, defaultJudgeWeights } from "../src/index";

describe("calculateFitness", () => {
  it("uses the approved weighted formula", () => {
    const fitness = calculateFitness(
      {
        logicalConsistency: 0.9,
        evidenceGrounding: 0.5,
        solutionUsefulness: 0.8
      },
      defaultJudgeWeights
    );

    expect(fitness).toBeCloseTo(0.79, 5);
  });
});
