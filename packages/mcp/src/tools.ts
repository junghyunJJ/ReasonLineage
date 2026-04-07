import {
  calculateFitness,
  evaluateBenchmarkAnswer,
  createCandidate,
  resolveWeights,
  type Candidate,
  type ScoredCandidate,
  type BenchmarkVerdict,
  type JudgeWeights,
  type QuestionCategory
} from "@reasonforge/core";

import {
  createSession,
  getSession,
  updateSession,
  touchSession,
  type SessionConfig,
  type SessionState
} from "./session.js";
import { shouldTerminate } from "./termination.js";

// --- Helper ---

function getSessionOrThrow(sessionId: string) {
  const session = getSession(sessionId);
  if (!session) {
    throw new Error(`Session not found: ${sessionId}`);
  }
  return session;
}

function assertNotTerminal(session: SessionState): void {
  if (session.status === "completed" || session.status === "failed") {
    throw new Error(`Session is already ${session.status}. No further operations allowed.`);
  }
}

function assertUniqueCandidateId(session: SessionState, candidateId: string): void {
  const existsInPopulation = session.population.some((c) => c.id === candidateId);
  const existsInPending = session.pendingCandidates.some((c) => c.id === candidateId);
  if (existsInPopulation || existsInPending) {
    throw new Error(`Candidate ID "${candidateId}" already exists in session. Use a unique ID.`);
  }
}

function makeBenchmarkVerdict(session: ReturnType<typeof getSession>, answer: string): BenchmarkVerdict {
  if (!session) throw new Error("Session is null");
  if (session.config.benchmark) {
    return evaluateBenchmarkAnswer(session.config.benchmark, answer);
  }
  return { passed: true, expectedAnswer: "", normalizedAnswer: "" };
}

function makeScoredCandidate(
  candidate: Candidate,
  scores: Record<string, number>,
  critique: string[],
  fitness: number,
  benchmarkVerdict: BenchmarkVerdict
): ScoredCandidate {
  return {
    ...candidate,
    logicalConsistency: scores.logicalConsistency ?? 0,
    evidenceGrounding: scores.evidenceGrounding ?? 0,
    solutionUsefulness: scores.solutionUsefulness ?? 0,
    scores,
    fitness,
    critique,
    benchmarkVerdict
  };
}

// --- Tool Handlers ---

export function handleStartSession(input: {
  threshold: number;
  populationLimit: number;
  generationLimit: number;
  survivorCount?: number;
  category?: string;
  weights?: Record<string, number>;
  benchmark?: { id: string; label: string; prompt: string; expectedAnswer: string };
  candidates: Array<{ id: string; answer: string }>;
  stagnationThreshold?: number;
  stagnationWindow?: number;
}) {
  const weights: JudgeWeights = resolveWeights({
    weights: input.weights as JudgeWeights | undefined,
    category: input.category as QuestionCategory | undefined
  });
  const config: SessionConfig = {
    threshold: input.threshold,
    populationLimit: input.populationLimit,
    generationLimit: input.generationLimit,
    survivorCount: input.survivorCount,
    weights,
    benchmark: input.benchmark,
    stagnationThreshold: input.stagnationThreshold,
    stagnationWindow: input.stagnationWindow,
  };

  if (input.candidates.length > input.populationLimit) {
    throw new Error(`Too many seed candidates (${input.candidates.length}). Maximum is ${input.populationLimit}.`);
  }

  const seenIds = new Set<string>();
  for (const c of input.candidates) {
    if (seenIds.has(c.id)) {
      throw new Error(`Duplicate candidate ID "${c.id}" in seed candidates.`);
    }
    seenIds.add(c.id);
  }

  const seedCandidates = input.candidates.map((c) => createCandidate(c.id, c.answer));
  const session = createSession(config, seedCandidates);

  return {
    content: [{
      type: "text" as const,
      text: JSON.stringify({
        sessionId: session.id,
        candidateCount: session.pendingCandidates.length,
        resolvedCategory: input.weights && Object.keys(input.weights).length > 0 ? "custom" : (input.category ?? "general"),
        weightDimensions: Object.keys(weights),
        message: `Session created. Score each candidate using reasonforge_score_candidate.`
      }, null, 2)
    }]
  };
}

export function handleScoreCandidate(input: {
  sessionId: string;
  candidateId: string;
  scores: Record<string, number>;
  critique: string[];
}) {
  const session = getSessionOrThrow(input.sessionId);
  touchSession(input.sessionId);
  assertNotTerminal(session);

  if (session.status !== "scoring" && session.status !== "mutating") {
    throw new Error(`Cannot score in "${session.status}" phase. Submit mutations or crossovers first, or check next step.`);
  }

  // Auto-transition from mutating to scoring at the BEGINNING
  if (session.status === "mutating") {
    updateSession(input.sessionId, (s) => ({ ...s, status: "scoring" as const }));
  }

  // Validate score dimensions match session weights
  const weightKeys = Object.keys(session.config.weights).filter(k => session.config.weights[k] != null);
  const scoreKeys = Object.keys(input.scores);
  const missing = weightKeys.filter(k => !scoreKeys.includes(k));
  if (missing.length > 0) {
    throw new Error(`Missing score dimensions: ${missing.join(", ")}. Expected all of: ${weightKeys.join(", ")}`);
  }

  const pendingIndex = session.pendingCandidates.findIndex((c) => c.id === input.candidateId);
  if (pendingIndex === -1) {
    // Check if already scored
    const alreadyScored = session.population.find((c) => c.id === input.candidateId);
    if (alreadyScored) {
      throw new Error(`Candidate ${input.candidateId} is already scored (fitness: ${alreadyScored.fitness.toFixed(3)})`);
    }
    throw new Error(`Candidate ${input.candidateId} not found in pending candidates. Available: ${session.pendingCandidates.map((c) => c.id).join(", ")}`);
  }

  const budget = session.config.populationLimit * session.config.generationLimit;
  if (session.evaluationCount >= budget) {
    throw new Error(`Evaluation budget (${budget}) exhausted for this session`);
  }

  const candidate = session.pendingCandidates[pendingIndex];
  const fitness = calculateFitness(session.config.weights, input.scores);
  const benchmarkVerdict = makeBenchmarkVerdict(session, candidate.answer);
  const scored = makeScoredCandidate(candidate, input.scores, input.critique, fitness, benchmarkVerdict);

  updateSession(input.sessionId, (s) => ({
    ...s,
    population: [...s.population, scored],
    pendingCandidates: s.pendingCandidates.filter((_, i) => i !== pendingIndex),
    evaluationCount: (s.evaluationCount ?? 0) + 1
  }));

  // Auto-transition when all pending candidates are scored
  const updated = getSession(input.sessionId)!;
  if (updated.pendingCandidates.length === 0) {
    const best = [...updated.population].sort((a, b) => b.fitness - a.fitness)[0];
    const hasBenchmark = !!updated.config.benchmark;
    if (best && shouldTerminate(best, updated.config.threshold, hasBenchmark)) {
      updateSession(input.sessionId, (s) => ({ ...s, status: "completed" as const }));
    } else {
      updateSession(input.sessionId, (s) => ({ ...s, status: "ready_to_select" as const }));
    }
  }

  const current = getSession(input.sessionId)!;
  return {
    content: [{
      type: "text" as const,
      text: JSON.stringify({
        candidateId: scored.id,
        fitness: Number(scored.fitness.toFixed(4)),
        benchmarkPassed: benchmarkVerdict.passed,
        populationScoredCount: current.population.length,
        totalPending: current.pendingCandidates.length
      }, null, 2)
    }]
  };
}

export function handleSelect(input: {
  sessionId: string;
  survivorCount?: number;
}) {
  const session = getSessionOrThrow(input.sessionId);
  touchSession(input.sessionId);
  assertNotTerminal(session);

  if (session.status !== "ready_to_select") {
    throw new Error(`Cannot select in "${session.status}" phase. Score all candidates first.`);
  }

  if (session.generation >= session.config.generationLimit) {
    updateSession(input.sessionId, (s) => ({ ...s, status: "completed" as const }));
    const best = [...session.population].sort((a, b) => b.fitness - a.fitness)[0];
    return {
      content: [{
        type: "text" as const,
        text: JSON.stringify({
          generation: session.generation,
          status: "completed",
          reason: "generation_limit_reached",
          bestCandidate: best ? { id: best.id, fitness: Number(best.fitness.toFixed(4)) } : null,
          message: `Generation limit (${session.config.generationLimit}) reached. Best candidate: "${best?.id ?? "none"}" with fitness ${best?.fitness.toFixed(4) ?? "N/A"}.`
        }, null, 2)
      }]
    };
  }

  if (session.population.length === 0) {
    throw new Error("Cannot select: no scored candidates in population");
  }

  const survivorCount = Math.min(
    input.survivorCount ?? session.config.survivorCount ?? 2,
    session.population.length
  );
  const sorted = [...session.population].sort((a, b) => b.fitness - a.fitness);
  const survivors = sorted.slice(0, survivorCount);
  const eliminated = sorted.slice(survivorCount);

  updateSession(input.sessionId, (s) => {
    const bestFitness = survivors[0]?.fitness ?? 0;
    return {
      ...s,
      generation: s.generation + 1,
      population: survivors,
      status: "mutating" as const,
      bestFitnessHistory: [...s.bestFitnessHistory, bestFitness]
    };
  });

  const updated = getSession(input.sessionId)!;
  return {
    content: [{
      type: "text" as const,
      text: JSON.stringify({
        generation: updated.generation,
        survivors: survivors.map((c) => ({ id: c.id, fitness: Number(c.fitness.toFixed(4)) })),
        eliminated: eliminated.map((c) => ({ id: c.id, fitness: Number(c.fitness.toFixed(4)) }))
      }, null, 2)
    }]
  };
}

export function handleMutate(input: {
  sessionId: string;
  parentId: string;
  candidateId: string;
  answer: string;
}) {
  const session = getSessionOrThrow(input.sessionId);
  touchSession(input.sessionId);
  assertNotTerminal(session);

  if (session.status !== "mutating") {
    throw new Error(`Cannot mutate in "${session.status}" phase.`);
  }

  const totalCandidates = session.population.length + session.pendingCandidates.length;
  if (totalCandidates >= session.config.populationLimit) {
    throw new Error(`Population limit (${session.config.populationLimit}) reached. Cannot add more candidates.`);
  }

  const parent = session.population.find((c) => c.id === input.parentId);
  if (!parent) {
    throw new Error(`Parent ${input.parentId} not found in population. Available: ${session.population.map((c) => c.id).join(", ")}`);
  }

  assertUniqueCandidateId(session, input.candidateId);

  const newCandidate = createCandidate(input.candidateId, input.answer, [input.parentId]);
  updateSession(input.sessionId, (s) => ({
    ...s,
    pendingCandidates: [...s.pendingCandidates, newCandidate]
  }));

  return {
    content: [{
      type: "text" as const,
      text: JSON.stringify({
        candidateId: input.candidateId,
        parentId: input.parentId,
        message: `Mutation registered. Score this candidate using reasonforge_score_candidate.`
      }, null, 2)
    }]
  };
}

export function handleCrossover(input: {
  sessionId: string;
  parentIds: [string, string];
  candidateId: string;
  answer: string;
}) {
  const session = getSessionOrThrow(input.sessionId);
  touchSession(input.sessionId);
  assertNotTerminal(session);

  if (session.status !== "mutating") {
    throw new Error(`Cannot crossover in "${session.status}" phase.`);
  }

  const totalCandidates = session.population.length + session.pendingCandidates.length;
  if (totalCandidates >= session.config.populationLimit) {
    throw new Error(`Population limit (${session.config.populationLimit}) reached. Cannot add more candidates.`);
  }

  for (const parentId of input.parentIds) {
    const parent = session.population.find((c) => c.id === parentId);
    if (!parent) {
      throw new Error(`Parent ${parentId} not found in population. Available: ${session.population.map((c) => c.id).join(", ")}`);
    }
  }

  assertUniqueCandidateId(session, input.candidateId);

  const newCandidate = createCandidate(input.candidateId, input.answer, [...input.parentIds]);
  updateSession(input.sessionId, (s) => ({
    ...s,
    pendingCandidates: [...s.pendingCandidates, newCandidate]
  }));

  return {
    content: [{
      type: "text" as const,
      text: JSON.stringify({
        candidateId: input.candidateId,
        parentIds: input.parentIds,
        message: `Crossover registered. Score this candidate using reasonforge_score_candidate.`
      }, null, 2)
    }]
  };
}

export function handleNextStep(input: { sessionId: string }) {
  const session = getSessionOrThrow(input.sessionId);
  touchSession(input.sessionId);

  const best = session.population.length > 0
    ? [...session.population].sort((a, b) => b.fitness - a.fitness)[0]
    : null;

  const hasBenchmark = !!session.config.benchmark;
  const thresholdMet = best
    ? shouldTerminate(best, session.config.threshold, hasBenchmark)
    : false;
  const generationLimitReached = session.generation >= session.config.generationLimit;

  // Stagnation detection
  const history = session.bestFitnessHistory;
  const window = session.config.stagnationWindow ?? 2;
  const stagnationThreshold = session.config.stagnationThreshold ?? 0.02;
  let stagnationDetected = false;
  if (history.length >= window + 1) {
    const recent = history.slice(-window - 1);
    const deltas = recent.slice(1).map((v, i) => v - recent[i]);
    stagnationDetected = deltas.every(d => Math.abs(d) < stagnationThreshold);
  }

  // Determine suggestion based on session phase
  let suggestion: {
    suggestedTool: string | null;
    suggestedArgs?: Record<string, unknown>;
    explanation: string;
  };

  if (session.status === "completed" || session.status === "failed") {
    // Branch 1: Terminal state
    suggestion = {
      suggestedTool: null,
      explanation: session.status === "completed" && thresholdMet
        ? `Threshold met! Best answer is "${best!.id}" with fitness ${best!.fitness.toFixed(4)}. The evolution cycle is complete.`
        : `Session ${session.status}. Best answer is "${best?.id ?? "none"}" with fitness ${best?.fitness.toFixed(4) ?? "N/A"}.`
    };
  } else if (generationLimitReached && session.pendingCandidates.length === 0) {
    // Branch 2: Generation limit reached -- finalize
    const newStatus = best ? "completed" : "failed";
    suggestion = {
      suggestedTool: null,
      explanation: best
        ? `Generation limit reached (${session.config.generationLimit}). Best answer is "${best.id}" with fitness ${best.fitness.toFixed(4)}.`
        : `Generation limit reached with no scored candidates. Session failed.`
    };
    updateSession(input.sessionId, (s) => ({ ...s, status: newStatus as "completed" | "failed" }));
  } else if (session.status === "scoring") {
    // Branch 3: Pending candidates need scoring
    const nextPending = session.pendingCandidates[0];
    suggestion = {
      suggestedTool: "reasonforge_score_candidate",
      suggestedArgs: {
        sessionId: session.id,
        candidateId: nextPending.id
      },
      explanation: `Score the ${session.pendingCandidates.length} pending candidate(s). Next: "${nextPending.id}". Score each dimension from 0 to 1.`
    };
  } else if (session.status === "ready_to_select") {
    // Branch 4: All scored, need selection
    suggestion = {
      suggestedTool: "reasonforge_select",
      suggestedArgs: { sessionId: session.id },
      explanation: `All ${session.population.length} candidates scored. Run selection to pick survivors and advance to generation ${session.generation + 1}.`
    };
  } else if (session.status === "mutating") {
    // Branch 5: After selection, need mutation/crossover
    const hasPending = session.pendingCandidates.length > 0;
    const stagnationNote = stagnationDetected
      ? ` Stagnation detected (fitness plateau for ${window} generations). Consider a fresh seed or radical mutation.`
      : "";
    suggestion = {
      suggestedTool: hasPending ? "reasonforge_score_candidate" : "reasonforge_mutate",
      suggestedArgs: hasPending
        ? { sessionId: session.id, candidateId: session.pendingCandidates[0].id }
        : { sessionId: session.id, parentId: best?.id },
      explanation: hasPending
        ? `${session.pendingCandidates.length} pending candidate(s) from mutations. You can score them now or submit more mutations/crossovers first. To score, use reasonforge_score_candidate.${stagnationNote}`
        : `Selection complete (Gen ${session.generation}). Submit mutations for the best candidate "${best?.id ?? ""}". Optionally use reasonforge_crossover to combine top candidates.${stagnationNote}`
    };
  } else {
    // Fallback (should not reach here)
    suggestion = {
      suggestedTool: null,
      explanation: `Session is in "${session.status}" phase.`
    };
  }

  // Re-read session to capture any status updates made above
  const current = getSession(input.sessionId) ?? session;

  return {
    content: [{
      type: "text" as const,
      text: JSON.stringify({
        sessionId: current.id,
        generation: current.generation,
        populationSize: current.population.length,
        pendingCount: current.pendingCandidates.length,
        bestFitness: best ? Number(best.fitness.toFixed(4)) : null,
        bestCandidateId: best?.id ?? null,
        thresholdMet,
        benchmarkPassed: best && hasBenchmark ? best.benchmarkVerdict.passed : null,
        generationLimitReached,
        stagnationDetected,
        status: current.status,
        suggestion
      }, null, 2)
    }]
  };
}
