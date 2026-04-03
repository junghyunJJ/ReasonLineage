import { describe, expect, it } from "vitest";

import {
  evaluateBenchmarkAnswer,
  getDefaultBenchmarkCase
} from "../src/index";

describe("evaluateBenchmarkAnswer", () => {
  it("marks the seeded ReasonForge benchmark as failed when the final answer is not drive", () => {
    const benchmark = getDefaultBenchmarkCase();

    const verdict = evaluateBenchmarkAnswer(benchmark, "You should walk.");

    expect(verdict.passed).toBe(false);
    expect(verdict.expectedAnswer).toBe("drive");
  });

  it("marks the seeded ReasonForge benchmark as passed when the final answer selects drive", () => {
    const benchmark = getDefaultBenchmarkCase();

    const verdict = evaluateBenchmarkAnswer(
      benchmark,
      "Drive there, wash the car, and come right back."
    );

    expect(verdict.passed).toBe(true);
    expect(verdict.expectedAnswer).toBe("drive");
  });
});
