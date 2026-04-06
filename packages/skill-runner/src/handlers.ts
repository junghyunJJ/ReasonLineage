import {
  calculateFitness,
  evaluateBenchmarkAnswer,
  createCandidate,
  resolveWeights,
  type ScoredCandidate,
  type BenchmarkVerdict,
  type JudgeWeights,
  type QuestionCategory
} from "@reasonforge/core";

import {
  createSessionFile,
  readSessionFile,
  writeSessionFile,
  type SessionConfig,
  type SessionState
} from "./state.js";

// --- Helpers (ported from tools.ts) ---

function getSessionOrThrow(sessionId: string): SessionState {
  const session = readSessionFile(sessionId);
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

function makeBenchmarkVerdict(session: SessionState, answer: string): BenchmarkVerdict {
  if (session.config.benchmark) {
    return evaluateBenchmarkAnswer(session.config.benchmark, answer);
  }
  return { passed: true, expectedAnswer: "", normalizedAnswer: "" };
}

function shouldTerminate(
  best: ScoredCandidate,
  threshold: number,
  hasBenchmark: boolean
): boolean {
  if (best.fitness < threshold) return false;
  if (hasBenchmark) return best.benchmarkVerdict.passed;
  return true;
}

function makeScoredCandidate(
  candidate: { id: string; answer: string },
  scores: Record<string, number>,
  critique: string[],
  fitness: number,
  benchmarkVerdict: BenchmarkVerdict
): ScoredCandidate {
  return {
    id: candidate.id,
    answer: candidate.answer,
    logicalConsistency: scores.logicalConsistency ?? 0,
    evidenceGrounding: scores.evidenceGrounding ?? 0,
    solutionUsefulness: scores.solutionUsefulness ?? 0,
    scores,
    fitness,
    critique,
    benchmarkVerdict
  };
}

// --- Handlers ---

export function handleInit(input: {
  threshold: number;
  populationLimit: number;
  generationLimit: number;
  category?: string;
  weights?: Record<string, number>;
  benchmark?: { id: string; label: string; prompt: string; expectedAnswer: string };
  candidates: Array<{ id: string; answer: string }>;
}) {
  const weights: JudgeWeights = resolveWeights({
    weights: input.weights as JudgeWeights | undefined,
    category: input.category as QuestionCategory | undefined
  });
  const config: SessionConfig = {
    threshold: input.threshold,
    populationLimit: input.populationLimit,
    generationLimit: input.generationLimit,
    weights,
    benchmark: input.benchmark
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
  const session = createSessionFile(config, seedCandidates);

  return {
    sessionId: session.id,
    candidateCount: session.pendingCandidates.length,
    resolvedCategory: input.weights && Object.keys(input.weights).length > 0 ? "custom" : (input.category ?? "general"),
    weightDimensions: Object.keys(weights),
    message: "Session created. Score each candidate using the score subcommand."
  };
}

export function handleScore(input: {
  sessionId: string;
  candidateId: string;
  scores: Record<string, number>;
  critique: string[];
}) {
  const session = getSessionOrThrow(input.sessionId);
  assertNotTerminal(session);

  if (session.status !== "scoring") {
    throw new Error(`Cannot score in "${session.status}" phase. Submit mutations or crossovers first.`);
  }

  const pendingIndex = session.pendingCandidates.findIndex((c) => c.id === input.candidateId);
  if (pendingIndex === -1) {
    const alreadyScored = session.population.find((c) => c.id === input.candidateId);
    if (alreadyScored) {
      throw new Error(`Candidate ${input.candidateId} is already scored (fitness: ${alreadyScored.fitness.toFixed(3)})`);
    }
    throw new Error(`Candidate ${input.candidateId} not found in pending candidates. Available: ${session.pendingCandidates.map((c) => c.id).join(", ")}`);
  }

  const candidate = session.pendingCandidates[pendingIndex];
  const missingDims = Object.keys(session.config.weights).filter(k => !(k in input.scores));
  if (missingDims.length > 0) {
    throw new Error(`Missing score dimensions: ${missingDims.join(', ')}`);
  }
  const fitness = calculateFitness(session.config.weights, input.scores);
  const benchmarkVerdict = makeBenchmarkVerdict(session, candidate.answer);
  const scored = makeScoredCandidate(candidate, input.scores, input.critique, fitness, benchmarkVerdict);

  session.population.push(scored);
  session.pendingCandidates.splice(pendingIndex, 1);

  // Auto-transition when all pending candidates are scored
  if (session.pendingCandidates.length === 0) {
    const best = [...session.population].sort((a, b) => b.fitness - a.fitness)[0];
    const hasBenchmark = !!session.config.benchmark;
    if (best && shouldTerminate(best, session.config.threshold, hasBenchmark)) {
      session.status = "completed";
    } else {
      session.status = "ready_to_select";
    }
  }

  writeSessionFile(input.sessionId, session);

  return {
    candidateId: scored.id,
    fitness: Number(scored.fitness.toFixed(4)),
    benchmarkPassed: benchmarkVerdict.passed,
    populationScoredCount: session.population.length,
    totalPending: session.pendingCandidates.length
  };
}

export function handleSelect(input: {
  sessionId: string;
  survivorCount?: number;
}) {
  const session = getSessionOrThrow(input.sessionId);
  assertNotTerminal(session);

  if (session.status !== "ready_to_select") {
    throw new Error(`Cannot select in "${session.status}" phase. Score all candidates first.`);
  }

  if (session.generation >= session.config.generationLimit) {
    throw new Error(`Generation limit (${session.config.generationLimit}) reached. Session should be finalized.`);
  }

  if (session.population.length === 0) {
    throw new Error("Cannot select: no scored candidates in population");
  }

  const survivorCount = Math.min(
    input.survivorCount ?? 2,
    session.population.length
  );
  const sorted = [...session.population].sort((a, b) => b.fitness - a.fitness);
  const survivors = sorted.slice(0, survivorCount);
  const eliminated = sorted.slice(survivorCount);

  session.generation += 1;
  session.population = survivors;
  session.status = "mutating";

  writeSessionFile(input.sessionId, session);

  return {
    generation: session.generation,
    survivors: survivors.map((c) => ({ id: c.id, fitness: Number(c.fitness.toFixed(4)) })),
    eliminated: eliminated.map((c) => ({ id: c.id, fitness: Number(c.fitness.toFixed(4)) }))
  };
}

export function handleMutate(input: {
  sessionId: string;
  parentId: string;
  candidateId: string;
  answer: string;
}) {
  const session = getSessionOrThrow(input.sessionId);
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

  const newCandidate = createCandidate(input.candidateId, input.answer);
  session.pendingCandidates.push(newCandidate);
  session.status = "scoring";

  writeSessionFile(input.sessionId, session);

  return {
    candidateId: input.candidateId,
    parentId: input.parentId,
    message: "Mutation registered. Score this candidate using the score subcommand."
  };
}

export function handleCrossover(input: {
  sessionId: string;
  parentIds: [string, string];
  candidateId: string;
  answer: string;
}) {
  const session = getSessionOrThrow(input.sessionId);
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

  const newCandidate = createCandidate(input.candidateId, input.answer);
  session.pendingCandidates.push(newCandidate);
  session.status = "scoring";

  writeSessionFile(input.sessionId, session);

  return {
    candidateId: input.candidateId,
    parentIds: input.parentIds,
    message: "Crossover registered. Score this candidate using the score subcommand."
  };
}

export function handleNextStep(input: { sessionId: string }) {
  const session = getSessionOrThrow(input.sessionId);

  const best = session.population.length > 0
    ? [...session.population].sort((a, b) => b.fitness - a.fitness)[0]
    : null;

  const hasBenchmark = !!session.config.benchmark;
  const thresholdMet = best
    ? shouldTerminate(best, session.config.threshold, hasBenchmark)
    : false;
  const generationLimitReached = session.generation >= session.config.generationLimit;

  let suggestion: {
    suggestedAction: string | null;
    explanation: string;
  };

  if (session.status === "completed" || session.status === "failed") {
    suggestion = {
      suggestedAction: null,
      explanation: session.status === "completed" && thresholdMet
        ? `Threshold met! Best answer is "${best!.id}" with fitness ${best!.fitness.toFixed(4)}. The evolution cycle is complete.`
        : `Session ${session.status}. Best answer is "${best?.id ?? "none"}" with fitness ${best?.fitness.toFixed(4) ?? "N/A"}.`
    };
  } else if (generationLimitReached && session.pendingCandidates.length === 0) {
    session.status = "completed";
    writeSessionFile(input.sessionId, session);
    suggestion = {
      suggestedAction: null,
      explanation: `Generation limit reached (${session.config.generationLimit}). Best answer is "${best?.id ?? "none"}" with fitness ${best?.fitness.toFixed(4) ?? "N/A"}.`
    };
  } else if (session.status === "scoring") {
    const nextPending = session.pendingCandidates[0];
    suggestion = {
      suggestedAction: "score",
      explanation: `Score the ${session.pendingCandidates.length} pending candidate(s). Next: "${nextPending.id}".`
    };
  } else if (session.status === "ready_to_select") {
    suggestion = {
      suggestedAction: "select",
      explanation: `All ${session.population.length} candidates scored. Run selection to advance to generation ${session.generation + 1}.`
    };
  } else if (session.status === "mutating") {
    suggestion = {
      suggestedAction: "mutate",
      explanation: `Selection complete (Gen ${session.generation}). Submit mutations for the best candidate "${best?.id ?? ""}".`
    };
  } else {
    suggestion = {
      suggestedAction: null,
      explanation: `Session is in "${session.status}" phase.`
    };
  }

  return {
    sessionId: session.id,
    generation: session.generation,
    populationSize: session.population.length,
    pendingCount: session.pendingCandidates.length,
    bestFitness: best ? Number(best.fitness.toFixed(4)) : null,
    bestCandidateId: best?.id ?? null,
    bestAnswer: best?.answer ?? null,
    thresholdMet,
    generationLimitReached,
    status: session.status,
    suggestion
  };
}
