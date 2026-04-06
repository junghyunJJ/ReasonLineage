import type { JudgeWeights } from "./types.js";
import { defaultJudgeWeights } from "./scoring.js";

// --- Types ---

export type QuestionCategory =
  | "general"
  | "math"
  | "science"
  | "creative"
  | "ethical"
  | "coding"
  | "analytical"
  | "biomedical";

export type CategoryPreset = {
  readonly category: QuestionCategory;
  readonly description: string;
  readonly weights: JudgeWeights;
  readonly suggestedThreshold: number;
};

// --- Category Presets ---

export const CATEGORY_PRESETS: Record<QuestionCategory, CategoryPreset> = {
  general: {
    category: "general",
    description: "General reasoning, argumentation, opinion questions",
    weights: { logicalConsistency: 0.50, evidenceGrounding: 0.20, solutionUsefulness: 0.30 },
    suggestedThreshold: 0.75
  },
  math: {
    category: "math",
    description: "Proofs, calculations, equations, numerical problems",
    weights: { mathematicalRigor: 0.45, stepValidity: 0.30, solutionCompleteness: 0.25 },
    suggestedThreshold: 0.80
  },
  science: {
    category: "science",
    description: "Hypotheses, experiments, theories, research questions",
    weights: { technicalAccuracy: 0.35, evidenceBase: 0.30, methodologicalSoundness: 0.20, novelty: 0.15 },
    suggestedThreshold: 0.75
  },
  creative: {
    category: "creative",
    description: "Stories, poems, brainstorming, creative writing",
    weights: { creativity: 0.30, originality: 0.25, coherence: 0.25, expressiveQuality: 0.20 },
    suggestedThreshold: 0.70
  },
  ethical: {
    category: "ethical",
    description: "Moral dilemmas, policy debates, ethical reasoning",
    weights: { ethicalAlignment: 0.30, stakeholderConsideration: 0.25, practicalFeasibility: 0.25, argumentBalance: 0.20 },
    suggestedThreshold: 0.75
  },
  coding: {
    category: "coding",
    description: "Algorithms, implementations, debugging, code design",
    weights: { correctness: 0.40, efficiency: 0.20, readability: 0.20, edgeCaseHandling: 0.20 },
    suggestedThreshold: 0.80
  },
  analytical: {
    category: "analytical",
    description: "Data analysis, reports, comparisons, assessments",
    weights: { accuracy: 0.35, completeness: 0.25, clarity: 0.25, insightDepth: 0.15 },
    suggestedThreshold: 0.75
  },
  biomedical: {
    category: "biomedical",
    description: "Drug targets, biomarkers, clinical hypotheses",
    weights: { evidenceCoverage: 0.30, specificity: 0.30, novelty: 0.20, actionability: 0.20 },
    suggestedThreshold: 0.75
  }
};

// --- Functions ---

export function getPresetWeights(category: QuestionCategory): JudgeWeights {
  const preset = CATEGORY_PRESETS[category];
  if (!preset) {
    throw new Error(`Unknown category: "${category}". Available: ${Object.keys(CATEGORY_PRESETS).join(", ")}`);
  }
  return { ...preset.weights };
}

export function resolveWeights(options: {
  weights?: JudgeWeights;
  category?: QuestionCategory;
}): JudgeWeights {
  if (options.weights && Object.keys(options.weights).length > 0) {
    return options.weights;
  }
  if (options.category) {
    return getPresetWeights(options.category);
  }
  return { ...defaultJudgeWeights };
}

export function getAllCategories(): readonly CategoryPreset[] {
  return Object.values(CATEGORY_PRESETS);
}

// --- Keyword-based classifier (convenience fallback) ---

const CATEGORY_PATTERNS: Array<{ category: QuestionCategory; patterns: RegExp[] }> = [
  {
    category: "math",
    patterns: [
      /\b(prove|proof|theorem|lemma)\b/i,
      /\b(calculate|compute|evaluate)\b/i,
      /\b(equation|integral|derivative|differential)\b/i,
      /\b(sum|product|limit|converge)\b/i,
      /\b(solve\s+for)\b/i,
      /\b(mathematical|algebra|geometry|trigonometry|calculus)\b/i,
      /\b(matrix|vector|determinant|eigenvalue)\b/i,
      /\b(sqrt|factorial|logarithm)\b/i
    ]
  },
  {
    category: "coding",
    patterns: [
      /\b(implement|code|program|function|method|class)\b/i,
      /\b(algorithm|data\s*structure|complexity)\b/i,
      /\b(debug|refactor|optimize)\b/i,
      /\b(python|javascript|typescript|java|rust|go|c\+\+)\b/i,
      /\b(api|endpoint|database|query)\b/i
    ]
  },
  {
    category: "biomedical",
    patterns: [
      /\b(drug\s*targets?|biomarker|therapeutic)\b/i,
      /\b(clinical\s*trial|patient|disease|treatment)\b/i,
      /\b(gene|protein|receptor|ligand|pathway)\b/i,
      /\b(pharmacology|toxicology|dosage)\b/i
    ]
  },
  {
    category: "science",
    patterns: [
      /\b(hypothesis|experiment|theory|scientific)\b/i,
      /\b(research|methodology|empirical)\b/i,
      /\b(mechanism|phenomenon|observation)\b/i,
      /\b(physics|chemistry|biology|ecology)\b/i
    ]
  },
  {
    category: "creative",
    patterns: [
      /\b(write\s+a\s+story|poem|creative\s*writing)\b/i,
      /\b(imagine|fiction|narrative|novel)\b/i,
      /\b(brainstorm|ideate|creative)\b/i,
      /\b(compose|lyric|screenplay|dialogue)\b/i
    ]
  },
  {
    category: "ethical",
    patterns: [
      /\b(ethical|moral|dilemma)\b/i,
      /\b(should\s+we|right\s+or\s+wrong|justice)\b/i,
      /\b(policy|regulation|fairness)\b/i,
      /\b(stakeholder|consequence|utilitarian|deontolog)/i
    ]
  },
  {
    category: "analytical",
    patterns: [
      /\b(analyze|analyse|assessment|evaluation)\b/i,
      /\b(compare\s+and\s+contrast|pros\s+and\s+cons)\b/i,
      /\b(report|survey|benchmark|metric)\b/i,
      /\b(trend|pattern|insight|finding)\b/i
    ]
  }
];

export function classifyQuestion(question: string): QuestionCategory {
  let bestCategory: QuestionCategory = "general";
  let bestScore = 0;

  for (const { category, patterns } of CATEGORY_PATTERNS) {
    const matchCount = patterns.filter(p => p.test(question)).length;
    if (matchCount > bestScore) {
      bestScore = matchCount;
      bestCategory = category;
    }
  }

  return bestCategory;
}
