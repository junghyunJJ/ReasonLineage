import { describe, expect, it } from "vitest";

import {
  evaluateBenchmarkAnswer,
  getDefaultBenchmarkCase,
  type BenchmarkCase
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

  it("uses custom matcher when provided", () => {
    const benchmark: BenchmarkCase = {
      id: "test",
      label: "Test",
      prompt: "test",
      expectedAnswer: "yes",
      matcher: (expected, answer) => answer.toLowerCase() === expected.toLowerCase()
    };
    // exact match required - "yes indeed" should fail with custom matcher
    expect(evaluateBenchmarkAnswer(benchmark, "yes indeed").passed).toBe(false);
    expect(evaluateBenchmarkAnswer(benchmark, "yes").passed).toBe(true);
  });
});
