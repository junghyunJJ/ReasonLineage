import { z } from "zod";

const scoreValueSchema = z.number().min(0).max(1);

export const startSessionSchema = z.object({
  threshold: z.number().min(0).max(1).default(0.75),
  populationLimit: z.number().int().min(2).max(10).default(3),
  generationLimit: z.number().int().min(1).max(10).default(3),
  survivorCount: z.number().int().min(1).max(10).optional(),
  stagnationThreshold: z.number().min(0).max(1).default(0.02).optional(),
  stagnationWindow: z.number().int().min(1).max(5).default(2).optional(),
  category: z.enum([
    "general", "math", "science", "creative",
    "ethical", "coding", "analytical", "biomedical"
  ]).optional(),
  weights: z.record(z.string(), z.number().min(0)).optional(),
  benchmark: z.object({
    id: z.string(),
    label: z.string(),
    prompt: z.string(),
    expectedAnswer: z.string()
  }).optional(),
  candidates: z.array(z.object({
    id: z.string(),
    answer: z.string().max(20_000)
  })).min(1)
})
.refine(
  (data) => data.populationLimit * data.generationLimit <= 100,
  { message: "Total evaluations (populationLimit × generationLimit) cannot exceed 100" }
);

export const scoreCandidateSchema = z.object({
  sessionId: z.string(),
  candidateId: z.string(),
  scores: z.record(z.string(), scoreValueSchema)
    .refine(
      (scores) => Object.keys(scores).length >= 1,
      { message: "At least one score dimension is required" }
    ),
  critique: z.array(z.string()).min(1)
});

export const selectSchema = z.object({
  sessionId: z.string(),
  survivorCount: z.number().int().min(1).optional()
});

export const mutateSchema = z.object({
  sessionId: z.string(),
  parentId: z.string(),
  candidateId: z.string(),
  answer: z.string().max(20_000)
});

export const crossoverSchema = z.object({
  sessionId: z.string(),
  parentIds: z.tuple([z.string(), z.string()]),
  candidateId: z.string(),
  answer: z.string().max(20_000)
});

export const nextStepSchema = z.object({
  sessionId: z.string()
});
