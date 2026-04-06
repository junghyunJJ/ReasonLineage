import { describe, expect, it } from "vitest";

import {
  CATEGORY_PRESETS,
  resolveWeights,
  classifyQuestion,
  getPresetWeights,
  getAllCategories,
  defaultJudgeWeights
} from "../src/index";

describe("CATEGORY_PRESETS", () => {
  it("defines 8 built-in categories", () => {
    const categories = Object.keys(CATEGORY_PRESETS);
    expect(categories).toHaveLength(8);
    expect(categories).toEqual(
      expect.arrayContaining([
        "general", "math", "science", "creative",
        "ethical", "coding", "analytical", "biomedical"
      ])
    );
  });

  it("all preset weights sum to approximately 1.0", () => {
    for (const [category, preset] of Object.entries(CATEGORY_PRESETS)) {
      const sum = Object.values(preset.weights).reduce(
        (s, v) => s + (v ?? 0), 0
      );
      expect(sum).toBeCloseTo(1.0, 2);
    }
  });

  it("general preset matches defaultJudgeWeights", () => {
    const generalWeights = CATEGORY_PRESETS.general.weights;
    expect(generalWeights.logicalConsistency).toBe(defaultJudgeWeights.logicalConsistency);
    expect(generalWeights.evidenceGrounding).toBe(defaultJudgeWeights.evidenceGrounding);
    expect(generalWeights.solutionUsefulness).toBe(defaultJudgeWeights.solutionUsefulness);
  });
});

describe("getPresetWeights", () => {
  it("returns math dimensions for math category", () => {
    const weights = getPresetWeights("math");
    expect(weights).toHaveProperty("mathematicalRigor", 0.45);
    expect(weights).toHaveProperty("stepValidity", 0.30);
    expect(weights).toHaveProperty("solutionCompleteness", 0.25);
    expect(weights).not.toHaveProperty("logicalConsistency");
  });

  it("returns a copy, not the original object", () => {
    const a = getPresetWeights("coding");
    const b = getPresetWeights("coding");
    expect(a).toEqual(b);
    expect(a).not.toBe(b);
  });

  it("throws for unknown category", () => {
    expect(() => getPresetWeights("unknown" as any)).toThrow("Unknown category");
  });
});

describe("resolveWeights", () => {
  it("returns explicit weights when provided (highest priority)", () => {
    const custom = { myDim: 1.0 };
    const result = resolveWeights({ weights: custom, category: "math" });
    expect(result).toBe(custom);
  });

  it("returns category preset when only category is provided", () => {
    const result = resolveWeights({ category: "creative" });
    expect(result).toHaveProperty("creativity", 0.30);
    expect(result).toHaveProperty("originality", 0.25);
  });

  it("returns defaultJudgeWeights when neither is provided", () => {
    const result = resolveWeights({});
    expect(result.logicalConsistency).toBe(0.5);
    expect(result.evidenceGrounding).toBe(0.2);
    expect(result.solutionUsefulness).toBe(0.3);
  });

  it("ignores empty weights object and falls back to category", () => {
    const result = resolveWeights({ weights: {}, category: "coding" });
    expect(result).toHaveProperty("correctness", 0.40);
  });
});

describe("classifyQuestion", () => {
  it("classifies math questions", () => {
    expect(classifyQuestion("Prove that the sum of two even numbers is even")).toBe("math");
    expect(classifyQuestion("Calculate the integral of x^2 dx")).toBe("math");
    expect(classifyQuestion("Solve for x: 2x + 3 = 7")).toBe("math");
  });

  it("classifies coding questions", () => {
    expect(classifyQuestion("Implement a binary search algorithm in Python")).toBe("coding");
    expect(classifyQuestion("Debug this JavaScript function")).toBe("coding");
  });

  it("classifies creative questions", () => {
    expect(classifyQuestion("Write a story about a lonely astronaut")).toBe("creative");
    expect(classifyQuestion("Compose a poem about autumn")).toBe("creative");
  });

  it("classifies science questions", () => {
    expect(classifyQuestion("What is the mechanism behind the Doppler effect?")).toBe("science");
    expect(classifyQuestion("Design an experiment to test this hypothesis")).toBe("science");
  });

  it("classifies ethical questions", () => {
    expect(classifyQuestion("Is it ethical to use AI in hiring decisions?")).toBe("ethical");
    expect(classifyQuestion("Should we allow genetic modification of embryos? What are the moral implications?")).toBe("ethical");
  });

  it("classifies biomedical questions", () => {
    expect(classifyQuestion("Identify drug targets for EGFR-mutant lung cancer")).toBe("biomedical");
    expect(classifyQuestion("What biomarker can predict treatment response?")).toBe("biomedical");
  });

  it("classifies analytical questions", () => {
    expect(classifyQuestion("Analyze the trends in this dataset and compare the results")).toBe("analytical");
  });

  it("falls back to general for ambiguous questions", () => {
    expect(classifyQuestion("What is the best approach to this problem?")).toBe("general");
    expect(classifyQuestion("Help me with this")).toBe("general");
  });
});

describe("getAllCategories", () => {
  it("returns all 8 presets", () => {
    const all = getAllCategories();
    expect(all).toHaveLength(8);
    expect(all[0]).toHaveProperty("category");
    expect(all[0]).toHaveProperty("weights");
    expect(all[0]).toHaveProperty("description");
    expect(all[0]).toHaveProperty("suggestedThreshold");
  });
});
