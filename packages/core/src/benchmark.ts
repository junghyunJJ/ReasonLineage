import type { BenchmarkCase, BenchmarkVerdict } from "./types";

const defaultBenchmarkCase: BenchmarkCase = {
  id: "car-wash-drive",
  label: "Seeded car wash benchmark",
  prompt:
    "I want to wash my car. The car wash is 50 meters away. Should I walk or drive?",
  expectedAnswer: "drive"
};

function normalizeAnswer(answer: string) {
  return answer.toLowerCase().replace(/[^a-z0-9\s]/g, " ").replace(/\s+/g, " ").trim();
}

export function getDefaultBenchmarkCase(): BenchmarkCase {
  return defaultBenchmarkCase;
}

export function evaluateBenchmarkAnswer(
  benchmark: BenchmarkCase,
  answer: string
): BenchmarkVerdict {
  const normalizedAnswer = normalizeAnswer(answer);
  const expectedAnswer = benchmark.expectedAnswer.toLowerCase();

  return {
    passed: normalizedAnswer.includes(expectedAnswer),
    expectedAnswer,
    normalizedAnswer
  };
}
