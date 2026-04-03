import { z } from "zod";

const scoreValueSchema = z.number().min(0).max(1);

export const startSessionSchema = z.object({
  threshold: z.number().min(0).max(1).default(0.85),
  populationLimit: z.number().int().min(2).max(20).default(5),
  generationLimit: z.number().int().min(1).max(20).default(5),
  weights: z.record(z.string(), z.number().min(0)).optional(),
  benchmark: z.object({
    id: z.string(),
    label: z.string(),
    prompt: z.string(),
    expectedAnswer: z.string()
  }).optional(),
  candidates: z.array(z.object({
    id: z.string(),
    answer: z.string().max(100_000)
  })).min(1)
});

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
  answer: z.string().max(100_000)
});

export const crossoverSchema = z.object({
  sessionId: z.string(),
  parentIds: z.tuple([z.string(), z.string()]),
  candidateId: z.string(),
  answer: z.string().max(100_000)
});

export const nextStepSchema = z.object({
  sessionId: z.string()
});
