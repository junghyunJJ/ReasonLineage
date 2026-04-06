import { describe, it, expect, afterEach } from "vitest";
import {
  handleInit,
  handleScore,
  handleSelect,
  handleMutate,
  handleCrossover,
  handleNextStep,
  deleteSessionFile,
  readSessionFile
} from "../src/index.js";

const sessions: string[] = [];

function initSession(overrides: Record<string, unknown> = {}) {
  const result = handleInit({
    threshold: 0.85,
    populationLimit: 5,
    generationLimit: 3,
    candidates: [
      { id: "c1", answer: "Answer 1" },
      { id: "c2", answer: "Answer 2" },
      { id: "c3", answer: "Answer 3" }
    ],
    ...overrides
  });
  sessions.push(result.sessionId);
  return result;
}

afterEach(() => {
  for (const sid of sessions) {
    deleteSessionFile(sid);
  }
  sessions.length = 0;
});

describe("handleInit", () => {
  it("creates session with 3 candidates", () => {
    const result = initSession();
    expect(result.sessionId).toBeTruthy();
    expect(result.candidateCount).toBe(3);

    const state = readSessionFile(result.sessionId);
    expect(state).not.toBeNull();
    expect(state!.status).toBe("scoring");
    expect(state!.pendingCandidates).toHaveLength(3);
    expect(state!.population).toHaveLength(0);
  });

  it("rejects duplicate candidate IDs", () => {
    expect(() => handleInit({
      threshold: 0.85,
      populationLimit: 5,
      generationLimit: 3,
      candidates: [
        { id: "dup", answer: "A" },
        { id: "dup", answer: "B" }
      ]
    })).toThrow("Duplicate candidate ID");
  });

  it("rejects too many candidates", () => {
    expect(() => handleInit({
      threshold: 0.85,
      populationLimit: 2,
      generationLimit: 3,
      candidates: [
        { id: "a", answer: "A" },
        { id: "b", answer: "B" },
        { id: "c", answer: "C" }
      ]
    })).toThrow("Too many seed candidates");
  });
});

describe("handleScore", () => {
  it("scores all candidates and auto-transitions to ready_to_select", () => {
    const { sessionId } = initSession();
    const defaultScores = { logicalConsistency: 0.6, evidenceGrounding: 0.5, solutionUsefulness: 0.5 };

    handleScore({ sessionId, candidateId: "c1", scores: defaultScores, critique: ["OK"] });
    handleScore({ sessionId, candidateId: "c2", scores: defaultScores, critique: ["OK"] });
    const r3 = handleScore({ sessionId, candidateId: "c3", scores: defaultScores, critique: ["OK"] });

    expect(r3.totalPending).toBe(0);
    expect(r3.populationScoredCount).toBe(3);

    const state = readSessionFile(sessionId)!;
    expect(state.status).toBe("ready_to_select");
  });

  it("auto-completes when threshold is met", () => {
    const { sessionId } = initSession();
    const high = { logicalConsistency: 0.95, evidenceGrounding: 0.9, solutionUsefulness: 0.95 };
    const low = { logicalConsistency: 0.3, evidenceGrounding: 0.3, solutionUsefulness: 0.3 };

    handleScore({ sessionId, candidateId: "c1", scores: high, critique: ["Great"] });
    handleScore({ sessionId, candidateId: "c2", scores: low, critique: ["Bad"] });
    handleScore({ sessionId, candidateId: "c3", scores: low, critique: ["Bad"] });

    const state = readSessionFile(sessionId)!;
    expect(state.status).toBe("completed");
  });

  it("calculates fitness correctly", () => {
    const { sessionId } = initSession();
    // Default weights: lc=0.5, eg=0.2, su=0.3
    const r = handleScore({
      sessionId,
      candidateId: "c1",
      scores: { logicalConsistency: 0.8, evidenceGrounding: 0.6, solutionUsefulness: 0.7 },
      critique: ["Note"]
    });
    // 0.8*0.5 + 0.6*0.2 + 0.7*0.3 = 0.4 + 0.12 + 0.21 = 0.73
    expect(r.fitness).toBeCloseTo(0.73, 3);
  });

  it("rejects scoring in wrong phase", () => {
    const { sessionId } = initSession();
    const scores = { logicalConsistency: 0.5, evidenceGrounding: 0.5, solutionUsefulness: 0.5 };
    handleScore({ sessionId, candidateId: "c1", scores, critique: ["OK"] });
    handleScore({ sessionId, candidateId: "c2", scores, critique: ["OK"] });
    handleScore({ sessionId, candidateId: "c3", scores, critique: ["OK"] });

    // Now in ready_to_select, force to mutating via select
    handleSelect({ sessionId, survivorCount: 2 });

    // Now in mutating phase — scoring should fail
    expect(() => handleScore({
      sessionId,
      candidateId: "c1",
      scores,
      critique: ["OK"]
    })).toThrow('Cannot score in "mutating" phase');
  });

  it("rejects scoring already-scored candidate", () => {
    const { sessionId } = initSession();
    const scores = { logicalConsistency: 0.5, evidenceGrounding: 0.5, solutionUsefulness: 0.5 };
    handleScore({ sessionId, candidateId: "c1", scores, critique: ["OK"] });

    expect(() => handleScore({
      sessionId,
      candidateId: "c1",
      scores,
      critique: ["Again"]
    })).toThrow("already scored");
  });
});

describe("handleSelect", () => {
  function scoreAll(sessionId: string) {
    const scores = { logicalConsistency: 0.6, evidenceGrounding: 0.5, solutionUsefulness: 0.5 };
    const high = { logicalConsistency: 0.8, evidenceGrounding: 0.7, solutionUsefulness: 0.8 };
    handleScore({ sessionId, candidateId: "c1", scores, critique: ["OK"] });
    handleScore({ sessionId, candidateId: "c2", scores: high, critique: ["Good"] });
    handleScore({ sessionId, candidateId: "c3", scores, critique: ["OK"] });
  }

  it("selects top survivors and advances generation", () => {
    const { sessionId } = initSession();
    scoreAll(sessionId);

    const result = handleSelect({ sessionId, survivorCount: 2 });
    expect(result.generation).toBe(1);
    expect(result.survivors).toHaveLength(2);
    expect(result.eliminated).toHaveLength(1);
    expect(result.survivors[0].id).toBe("c2"); // highest fitness

    const state = readSessionFile(sessionId)!;
    expect(state.status).toBe("mutating");
    expect(state.generation).toBe(1);
    expect(state.population).toHaveLength(2);
  });

  it("rejects select when generation limit reached", () => {
    const { sessionId } = initSession({ generationLimit: 1 });
    scoreAll(sessionId);
    handleSelect({ sessionId, survivorCount: 2 });

    // Now generation=1, limit=1. Need to get back to ready_to_select
    handleMutate({ sessionId, parentId: "c2", candidateId: "m1", answer: "Mutated" });
    const scores = { logicalConsistency: 0.6, evidenceGrounding: 0.5, solutionUsefulness: 0.5 };
    handleScore({ sessionId, candidateId: "m1", scores, critique: ["OK"] });

    // Now ready_to_select but generation >= limit
    expect(() => handleSelect({ sessionId })).toThrow("Generation limit");
  });
});

describe("handleMutate", () => {
  function setupMutatingPhase() {
    const { sessionId } = initSession();
    const scores = { logicalConsistency: 0.6, evidenceGrounding: 0.5, solutionUsefulness: 0.5 };
    handleScore({ sessionId, candidateId: "c1", scores, critique: ["OK"] });
    handleScore({ sessionId, candidateId: "c2", scores, critique: ["OK"] });
    handleScore({ sessionId, candidateId: "c3", scores, critique: ["OK"] });
    handleSelect({ sessionId, survivorCount: 2 });
    return sessionId;
  }

  it("registers mutation and transitions to scoring", () => {
    const sessionId = setupMutatingPhase();
    const result = handleMutate({
      sessionId,
      parentId: "c1",
      candidateId: "m1",
      answer: "Improved answer"
    });

    expect(result.candidateId).toBe("m1");
    expect(result.parentId).toBe("c1");

    const state = readSessionFile(sessionId)!;
    expect(state.status).toBe("scoring");
    expect(state.pendingCandidates).toHaveLength(1);
    expect(state.pendingCandidates[0].id).toBe("m1");
  });

  it("rejects duplicate candidate ID", () => {
    const sessionId = setupMutatingPhase();
    expect(() => handleMutate({
      sessionId,
      parentId: "c1",
      candidateId: "c1", // already exists
      answer: "Dup"
    })).toThrow('already exists');
  });

  it("rejects unknown parent", () => {
    const sessionId = setupMutatingPhase();
    expect(() => handleMutate({
      sessionId,
      parentId: "nonexistent",
      candidateId: "m1",
      answer: "Test"
    })).toThrow("not found in population");
  });
});

describe("handleCrossover", () => {
  it("registers crossover from two parents", () => {
    const { sessionId } = initSession();
    const scores = { logicalConsistency: 0.6, evidenceGrounding: 0.5, solutionUsefulness: 0.5 };
    handleScore({ sessionId, candidateId: "c1", scores, critique: ["OK"] });
    handleScore({ sessionId, candidateId: "c2", scores, critique: ["OK"] });
    handleScore({ sessionId, candidateId: "c3", scores, critique: ["OK"] });
    handleSelect({ sessionId, survivorCount: 2 });

    const survivors = readSessionFile(sessionId)!.population.map((c) => c.id);
    const result = handleCrossover({
      sessionId,
      parentIds: [survivors[0], survivors[1]],
      candidateId: "cross-1",
      answer: "Combined answer"
    });

    expect(result.candidateId).toBe("cross-1");
    const state = readSessionFile(sessionId)!;
    expect(state.status).toBe("scoring");
    expect(state.pendingCandidates.some((c) => c.id === "cross-1")).toBe(true);
  });
});

describe("handleNextStep", () => {
  it("suggests score when in scoring phase", () => {
    const { sessionId } = initSession();
    const result = handleNextStep({ sessionId });
    expect(result.status).toBe("scoring");
    expect(result.suggestion.suggestedAction).toBe("score");
    expect(result.pendingCount).toBe(3);
  });

  it("suggests select when ready_to_select", () => {
    const { sessionId } = initSession();
    const scores = { logicalConsistency: 0.6, evidenceGrounding: 0.5, solutionUsefulness: 0.5 };
    handleScore({ sessionId, candidateId: "c1", scores, critique: ["OK"] });
    handleScore({ sessionId, candidateId: "c2", scores, critique: ["OK"] });
    handleScore({ sessionId, candidateId: "c3", scores, critique: ["OK"] });

    const result = handleNextStep({ sessionId });
    expect(result.status).toBe("ready_to_select");
    expect(result.suggestion.suggestedAction).toBe("select");
  });

  it("suggests mutate when in mutating phase", () => {
    const { sessionId } = initSession();
    const scores = { logicalConsistency: 0.6, evidenceGrounding: 0.5, solutionUsefulness: 0.5 };
    handleScore({ sessionId, candidateId: "c1", scores, critique: ["OK"] });
    handleScore({ sessionId, candidateId: "c2", scores, critique: ["OK"] });
    handleScore({ sessionId, candidateId: "c3", scores, critique: ["OK"] });
    handleSelect({ sessionId, survivorCount: 2 });

    const result = handleNextStep({ sessionId });
    expect(result.status).toBe("mutating");
    expect(result.suggestion.suggestedAction).toBe("mutate");
  });

  it("returns null action when completed", () => {
    const { sessionId } = initSession();
    const high = { logicalConsistency: 0.95, evidenceGrounding: 0.9, solutionUsefulness: 0.95 };
    const low = { logicalConsistency: 0.3, evidenceGrounding: 0.3, solutionUsefulness: 0.3 };
    handleScore({ sessionId, candidateId: "c1", scores: high, critique: ["Great"] });
    handleScore({ sessionId, candidateId: "c2", scores: low, critique: ["Bad"] });
    handleScore({ sessionId, candidateId: "c3", scores: low, critique: ["Bad"] });

    const result = handleNextStep({ sessionId });
    expect(result.status).toBe("completed");
    expect(result.thresholdMet).toBe(true);
    expect(result.suggestion.suggestedAction).toBeNull();
  });

  it("completes on generation limit", () => {
    const { sessionId } = initSession({ generationLimit: 1 });
    const scores = { logicalConsistency: 0.6, evidenceGrounding: 0.5, solutionUsefulness: 0.5 };
    handleScore({ sessionId, candidateId: "c1", scores, critique: ["OK"] });
    handleScore({ sessionId, candidateId: "c2", scores, critique: ["OK"] });
    handleScore({ sessionId, candidateId: "c3", scores, critique: ["OK"] });
    handleSelect({ sessionId, survivorCount: 2 });
    handleMutate({ sessionId, parentId: "c1", candidateId: "m1", answer: "Better" });
    handleScore({ sessionId, candidateId: "m1", scores, critique: ["OK"] });

    // generation=1, limit=1, no pending → next-step should complete
    const result = handleNextStep({ sessionId });
    expect(result.status).toBe("completed");
    expect(result.generationLimitReached).toBe(true);
  });
});

describe("custom dimensions", () => {
  it("calculates fitness with custom weights", () => {
    const { sessionId } = initSession({
      weights: { creativity: 0.5, depth: 0.3, clarity: 0.2 }
    });

    const result = handleScore({
      sessionId,
      candidateId: "c1",
      scores: { creativity: 0.8, depth: 0.6, clarity: 0.9 },
      critique: ["Creative"]
    });

    // 0.8*0.5 + 0.6*0.3 + 0.9*0.2 = 0.4 + 0.18 + 0.18 = 0.76
    expect(result.fitness).toBeCloseTo(0.76, 3);
  });
});

describe("benchmark integration", () => {
  it("populates benchmarkVerdict on scored candidates", () => {
    const { sessionId } = initSession({
      benchmark: {
        id: "test-bench",
        label: "Test",
        prompt: "What is 2+2?",
        expectedAnswer: "4"
      }
    });

    handleScore({
      sessionId,
      candidateId: "c1",
      scores: { logicalConsistency: 0.9, evidenceGrounding: 0.8, solutionUsefulness: 0.9 },
      critique: ["Good"]
    });

    const state = readSessionFile(sessionId)!;
    const scored = state.population.find((c) => c.id === "c1")!;
    expect(scored.benchmarkVerdict).toBeDefined();
    expect(typeof scored.benchmarkVerdict.passed).toBe("boolean");
  });
});
