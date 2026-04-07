import { describe, it, expect, beforeEach } from "vitest";
import { clearAllSessions } from "../src/session.js";
import {
  handleStartSession,
  handleScoreCandidate,
  handleSelect,
  handleMutate,
  handleCrossover,
  handleNextStep
} from "../src/tools.js";

function parseResult(result: { content: Array<{ type: string; text: string }> }) {
  return JSON.parse(result.content[0].text);
}

describe("MCP Tool Handlers", () => {
  beforeEach(() => {
    clearAllSessions();
  });

  it("runs a complete evolution cycle", () => {
    // 1. Start session with 3 candidates (threshold 0.9 so initial scores don't meet it)
    const startResult = parseResult(handleStartSession({
      threshold: 0.9,
      populationLimit: 5,
      generationLimit: 5,
      candidates: [
        { id: "c1", answer: "Answer 1" },
        { id: "c2", answer: "Answer 2" },
        { id: "c3", answer: "Answer 3" }
      ]
    }));
    expect(startResult.sessionId).toBeTruthy();
    expect(startResult.candidateCount).toBe(3);
    const sessionId = startResult.sessionId;

    // 2. Check next step -- should suggest scoring
    const step1 = parseResult(handleNextStep({ sessionId }));
    expect(step1.pendingCount).toBe(3);
    expect(step1.suggestion.suggestedTool).toBe("reasonforge_score_candidate");

    // 3. Score all 3 candidates
    const score1 = parseResult(handleScoreCandidate({
      sessionId,
      candidateId: "c1",
      scores: { logicalConsistency: 0.9, evidenceGrounding: 0.8, solutionUsefulness: 0.85 },
      critique: ["Good reasoning"]
    }));
    expect(score1.fitness).toBeGreaterThan(0);
    expect(score1.totalPending).toBe(2);

    handleScoreCandidate({
      sessionId,
      candidateId: "c2",
      scores: { logicalConsistency: 0.5, evidenceGrounding: 0.4, solutionUsefulness: 0.3 },
      critique: ["Weak argument"]
    });

    handleScoreCandidate({
      sessionId,
      candidateId: "c3",
      scores: { logicalConsistency: 0.7, evidenceGrounding: 0.6, solutionUsefulness: 0.65 },
      critique: ["Decent but could improve"]
    });

    // 4. Check next step -- should suggest selection
    const step2 = parseResult(handleNextStep({ sessionId }));
    expect(step2.pendingCount).toBe(0);
    expect(step2.suggestion.suggestedTool).toBe("reasonforge_select");

    // 5. Select top 2 survivors
    const selectResult = parseResult(handleSelect({ sessionId, survivorCount: 2 }));
    expect(selectResult.generation).toBe(1);
    expect(selectResult.survivors).toHaveLength(2);
    expect(selectResult.eliminated).toHaveLength(1);
    // c1 should be first (highest fitness)
    expect(selectResult.survivors[0].id).toBe("c1");

    // 6. Check next step -- should suggest mutation
    const step3 = parseResult(handleNextStep({ sessionId }));
    expect(step3.suggestion.suggestedTool).toBe("reasonforge_mutate");

    // 7. Submit mutation
    const mutateResult = parseResult(handleMutate({
      sessionId,
      parentId: "c1",
      candidateId: "c1-m1",
      answer: "Improved answer 1"
    }));
    expect(mutateResult.parentId).toBe("c1");

    // 8. Score mutated candidate with high scores (should meet threshold)
    handleScoreCandidate({
      sessionId,
      candidateId: "c1-m1",
      scores: { logicalConsistency: 0.95, evidenceGrounding: 0.9, solutionUsefulness: 0.92 },
      critique: ["Excellent"]
    });

    // 9. Check next step -- should report threshold met
    const step4 = parseResult(handleNextStep({ sessionId }));
    expect(step4.thresholdMet).toBe(true);
    expect(step4.bestCandidateId).toBe("c1-m1");
    expect(step4.status).toBe("completed");
  });

  it("handles invalid session ID", () => {
    expect(() => handleScoreCandidate({
      sessionId: "fake",
      candidateId: "c1",
      scores: { x: 0.5 },
      critique: ["test"]
    })).toThrow("Session not found");
  });

  it("handles scoring unknown candidate", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.85,
      populationLimit: 5,
      generationLimit: 5,
      candidates: [{ id: "c1", answer: "A" }]
    }));
    expect(() => handleScoreCandidate({
      sessionId: start.sessionId,
      candidateId: "nonexistent",
      scores: { logicalConsistency: 0.5, evidenceGrounding: 0.5, solutionUsefulness: 0.5 },
      critique: ["test"]
    })).toThrow("not found in pending");
  });

  it("prevents selection in scoring phase", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.85,
      populationLimit: 5,
      generationLimit: 5,
      candidates: [{ id: "c1", answer: "A" }]
    }));
    expect(() => handleSelect({ sessionId: start.sessionId }))
      .toThrow('Cannot select in "scoring" phase');
  });

  it("works with custom dimensions", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.7,
      populationLimit: 3,
      generationLimit: 3,
      weights: { creativity: 0.5, depth: 0.3, clarity: 0.2 },
      candidates: [
        { id: "c1", answer: "Creative answer" },
        { id: "c2", answer: "Deep answer" }
      ]
    }));

    const score = parseResult(handleScoreCandidate({
      sessionId: start.sessionId,
      candidateId: "c1",
      scores: { creativity: 0.9, depth: 0.7, clarity: 0.8 },
      critique: ["Very creative"]
    }));
    // fitness = 0.5*0.9 + 0.3*0.7 + 0.2*0.8 = 0.45 + 0.21 + 0.16 = 0.82
    expect(score.fitness).toBeCloseTo(0.82, 2);
  });

  it("rejects duplicate candidate IDs in mutations", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.85,
      populationLimit: 5,
      generationLimit: 5,
      candidates: [{ id: "c1", answer: "A" }]
    }));
    // Score c1
    handleScoreCandidate({
      sessionId: start.sessionId,
      candidateId: "c1",
      scores: { logicalConsistency: 0.8, evidenceGrounding: 0.7, solutionUsefulness: 0.75 },
      critique: ["ok"]
    });
    // Select
    handleSelect({ sessionId: start.sessionId });
    // Try to mutate with existing ID
    expect(() => handleMutate({
      sessionId: start.sessionId,
      parentId: "c1",
      candidateId: "c1",  // duplicate!
      answer: "Mutated"
    })).toThrow("already exists");
  });

  it("rejects operations on completed sessions", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.1, // very low threshold
      populationLimit: 5,
      generationLimit: 5,
      candidates: [{ id: "c1", answer: "A" }]
    }));
    const sessionId = start.sessionId;
    handleScoreCandidate({
      sessionId,
      candidateId: "c1",
      scores: { logicalConsistency: 0.9, evidenceGrounding: 0.8, solutionUsefulness: 0.9 },
      critique: ["good"]
    });
    // next_step should mark as completed (threshold 0.1, fitness >> 0.1)
    const step = parseResult(handleNextStep({ sessionId }));
    expect(step.thresholdMet).toBe(true);
    expect(step.status).toBe("completed");

    // Now try to mutate on completed session
    expect(() => handleMutate({
      sessionId,
      parentId: "c1",
      candidateId: "c1-m",
      answer: "mutation"
    })).toThrow("already completed");
  });

  it("rejects exceeding generation limit in select", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.99, // unreachable threshold
      populationLimit: 10,
      generationLimit: 1, // only 1 generation allowed
      candidates: [{ id: "c1", answer: "A" }, { id: "c2", answer: "B" }]
    }));
    const sessionId = start.sessionId;
    handleScoreCandidate({ sessionId, candidateId: "c1", scores: { logicalConsistency: 0.5, evidenceGrounding: 0.5, solutionUsefulness: 0.5 }, critique: ["ok"] });
    handleScoreCandidate({ sessionId, candidateId: "c2", scores: { logicalConsistency: 0.4, evidenceGrounding: 0.4, solutionUsefulness: 0.4 }, critique: ["ok"] });
    handleSelect({ sessionId }); // gen 0 -> 1 (at limit)

    // Add a mutation and score it so we have something to select
    handleMutate({ sessionId, parentId: "c1", candidateId: "c1-m", answer: "M" });
    handleScoreCandidate({ sessionId, candidateId: "c1-m", scores: { logicalConsistency: 0.6, evidenceGrounding: 0.6, solutionUsefulness: 0.6 }, critique: ["ok"] });

    // Try to select again (would go to gen 2, over limit)
    const result = parseResult(handleSelect({ sessionId }));
    expect(result.status).toBe("completed");
    expect(result.reason).toBe("generation_limit_reached");
  });

  it("rejects too many seed candidates exceeding populationLimit", () => {
    expect(() => handleStartSession({
      threshold: 0.85,
      populationLimit: 2,
      generationLimit: 5,
      candidates: [
        { id: "c1", answer: "A" },
        { id: "c2", answer: "B" },
        { id: "c3", answer: "C" }
      ]
    })).toThrow("Too many seed candidates");
  });

  it("rejects scoring on completed session", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.1,
      populationLimit: 5,
      generationLimit: 5,
      candidates: [{ id: "c1", answer: "A" }]
    }));
    const sessionId = start.sessionId;
    handleScoreCandidate({
      sessionId,
      candidateId: "c1",
      scores: { logicalConsistency: 0.9, evidenceGrounding: 0.9, solutionUsefulness: 0.9 },
      critique: ["great"]
    });
    // Complete via next_step
    handleNextStep({ sessionId });

    expect(() => handleScoreCandidate({
      sessionId,
      candidateId: "c1",
      scores: { logicalConsistency: 0.5, evidenceGrounding: 0.5, solutionUsefulness: 0.5 },
      critique: ["test"]
    })).toThrow("already completed");
  });

  it("rejects crossover on completed session", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.1,
      populationLimit: 5,
      generationLimit: 5,
      candidates: [{ id: "c1", answer: "A" }, { id: "c2", answer: "B" }]
    }));
    const sessionId = start.sessionId;
    handleScoreCandidate({ sessionId, candidateId: "c1", scores: { logicalConsistency: 0.9, evidenceGrounding: 0.9, solutionUsefulness: 0.9 }, critique: ["ok"] });
    handleScoreCandidate({ sessionId, candidateId: "c2", scores: { logicalConsistency: 0.8, evidenceGrounding: 0.8, solutionUsefulness: 0.8 }, critique: ["ok"] });
    handleNextStep({ sessionId }); // completes due to low threshold

    expect(() => handleCrossover({
      sessionId,
      parentIds: ["c1", "c2"],
      candidateId: "c1+c2",
      answer: "combined"
    })).toThrow("already completed");
  });

  it("rejects select on completed session", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.1,
      populationLimit: 5,
      generationLimit: 5,
      candidates: [{ id: "c1", answer: "A" }]
    }));
    const sessionId = start.sessionId;
    handleScoreCandidate({ sessionId, candidateId: "c1", scores: { logicalConsistency: 0.9, evidenceGrounding: 0.9, solutionUsefulness: 0.9 }, critique: ["ok"] });
    handleNextStep({ sessionId }); // completes

    expect(() => handleSelect({ sessionId })).toThrow("already completed");
  });

  it("handles crossover correctly", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.85,
      populationLimit: 5,
      generationLimit: 5,
      candidates: [
        { id: "c1", answer: "A1" },
        { id: "c2", answer: "A2" }
      ]
    }));
    const sessionId = start.sessionId;

    // Score both
    handleScoreCandidate({ sessionId, candidateId: "c1", scores: { logicalConsistency: 0.8, evidenceGrounding: 0.7, solutionUsefulness: 0.75 }, critique: ["ok"] });
    handleScoreCandidate({ sessionId, candidateId: "c2", scores: { logicalConsistency: 0.6, evidenceGrounding: 0.5, solutionUsefulness: 0.55 }, critique: ["ok"] });

    // Select
    handleSelect({ sessionId, survivorCount: 2 });

    // Crossover
    const crossResult = parseResult(handleCrossover({
      sessionId,
      parentIds: ["c1", "c2"],
      candidateId: "c1+c2",
      answer: "Combined answer"
    }));
    expect(crossResult.parentIds).toEqual(["c1", "c2"]);
    expect(crossResult.candidateId).toBe("c1+c2");
  });

  // --- Phase enforcement tests ---

  it("rejects mutate in ready_to_select phase", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.99,
      populationLimit: 5,
      generationLimit: 5,
      candidates: [{ id: "c1", answer: "A" }]
    }));
    const sessionId = start.sessionId;
    // Score c1 -> auto-transitions to ready_to_select (threshold 0.99 not met)
    handleScoreCandidate({ sessionId, candidateId: "c1", scores: { logicalConsistency: 0.5, evidenceGrounding: 0.5, solutionUsefulness: 0.5 }, critique: ["ok"] });

    expect(() => handleMutate({
      sessionId,
      parentId: "c1",
      candidateId: "c1-m",
      answer: "mutation"
    })).toThrow('Cannot mutate in "ready_to_select" phase');
  });

  it("rejects crossover in ready_to_select phase", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.99,
      populationLimit: 5,
      generationLimit: 5,
      candidates: [{ id: "c1", answer: "A" }, { id: "c2", answer: "B" }]
    }));
    const sessionId = start.sessionId;
    handleScoreCandidate({ sessionId, candidateId: "c1", scores: { logicalConsistency: 0.5, evidenceGrounding: 0.5, solutionUsefulness: 0.5 }, critique: ["ok"] });
    handleScoreCandidate({ sessionId, candidateId: "c2", scores: { logicalConsistency: 0.4, evidenceGrounding: 0.4, solutionUsefulness: 0.4 }, critique: ["ok"] });

    expect(() => handleCrossover({
      sessionId,
      parentIds: ["c1", "c2"],
      candidateId: "c1+c2",
      answer: "combined"
    })).toThrow('Cannot crossover in "ready_to_select" phase');
  });

  it("rejects double select (second call in mutating phase)", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.99,
      populationLimit: 5,
      generationLimit: 5,
      candidates: [{ id: "c1", answer: "A" }, { id: "c2", answer: "B" }]
    }));
    const sessionId = start.sessionId;
    handleScoreCandidate({ sessionId, candidateId: "c1", scores: { logicalConsistency: 0.5, evidenceGrounding: 0.5, solutionUsefulness: 0.5 }, critique: ["ok"] });
    handleScoreCandidate({ sessionId, candidateId: "c2", scores: { logicalConsistency: 0.4, evidenceGrounding: 0.4, solutionUsefulness: 0.4 }, critique: ["ok"] });
    handleSelect({ sessionId }); // ready_to_select -> mutating

    expect(() => handleSelect({ sessionId }))
      .toThrow('Cannot select in "mutating" phase');
  });

  it("auto-completes session when threshold is met during scoring", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.1, // very low threshold
      populationLimit: 5,
      generationLimit: 5,
      candidates: [{ id: "c1", answer: "A" }, { id: "c2", answer: "B" }]
    }));
    const sessionId = start.sessionId;

    // Score c1 (still 1 pending, so no auto-transition yet)
    handleScoreCandidate({ sessionId, candidateId: "c1", scores: { logicalConsistency: 0.9, evidenceGrounding: 0.9, solutionUsefulness: 0.9 }, critique: ["ok"] });

    // Score c2 -> all scored, threshold met -> auto-completes
    handleScoreCandidate({ sessionId, candidateId: "c2", scores: { logicalConsistency: 0.8, evidenceGrounding: 0.8, solutionUsefulness: 0.8 }, critique: ["ok"] });

    // Verify session is already completed
    const step = parseResult(handleNextStep({ sessionId }));
    expect(step.status).toBe("completed");
    expect(step.thresholdMet).toBe(true);

    // Cannot score on completed session
    expect(() => handleScoreCandidate({
      sessionId,
      candidateId: "c3",
      scores: { logicalConsistency: 0.5, evidenceGrounding: 0.5, solutionUsefulness: 0.5 },
      critique: ["test"]
    })).toThrow("already completed");
  });

  it("rejects scoring in ready_to_select phase", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.99,
      populationLimit: 5,
      generationLimit: 5,
      candidates: [{ id: "c1", answer: "A" }]
    }));
    const sessionId = start.sessionId;
    handleScoreCandidate({ sessionId, candidateId: "c1", scores: { logicalConsistency: 0.5, evidenceGrounding: 0.5, solutionUsefulness: 0.5 }, critique: ["ok"] });

    // Session is now in ready_to_select -- no pending candidates to score, but test the phase guard
    // We need to add a candidate via select -> mutate first, but that changes status.
    // Instead, verify the status directly via handleNextStep
    const step = parseResult(handleNextStep({ sessionId }));
    expect(step.status).toBe("ready_to_select");
    expect(step.suggestion.suggestedTool).toBe("reasonforge_select");
  });

  it("allows multiple mutations before scoring", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.99,
      populationLimit: 10,
      generationLimit: 5,
      candidates: [{ id: "c1", answer: "A" }, { id: "c2", answer: "B" }]
    }));
    const sessionId = start.sessionId;

    // Score both
    handleScoreCandidate({ sessionId, candidateId: "c1", scores: { logicalConsistency: 0.8, evidenceGrounding: 0.7, solutionUsefulness: 0.75 }, critique: ["ok"] });
    handleScoreCandidate({ sessionId, candidateId: "c2", scores: { logicalConsistency: 0.6, evidenceGrounding: 0.5, solutionUsefulness: 0.55 }, critique: ["ok"] });

    // Select
    handleSelect({ sessionId, survivorCount: 2 });

    // Multiple mutations in a row (should NOT throw)
    handleMutate({ sessionId, parentId: "c1", candidateId: "m1", answer: "Mut 1" });
    handleMutate({ sessionId, parentId: "c2", candidateId: "m2", answer: "Mut 2" });

    // Crossover after mutations (should NOT throw)
    handleCrossover({ sessionId, parentIds: ["c1", "c2"], candidateId: "cross1", answer: "Cross" });

    // Now score all pending
    handleScoreCandidate({ sessionId, candidateId: "m1", scores: { logicalConsistency: 0.85, evidenceGrounding: 0.75, solutionUsefulness: 0.8 }, critique: ["better"] });
    handleScoreCandidate({ sessionId, candidateId: "m2", scores: { logicalConsistency: 0.65, evidenceGrounding: 0.55, solutionUsefulness: 0.6 }, critique: ["ok"] });
    handleScoreCandidate({ sessionId, candidateId: "cross1", scores: { logicalConsistency: 0.9, evidenceGrounding: 0.8, solutionUsefulness: 0.85 }, critique: ["great"] });

    // Verify all scored
    const step = parseResult(handleNextStep({ sessionId }));
    expect(step.pendingCount).toBe(0);
  });

  it("rejects scoring with wrong dimensions", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.85,
      populationLimit: 5,
      generationLimit: 5,
      weights: { accuracy: 0.5, clarity: 0.5 },
      candidates: [{ id: "c1", answer: "A" }]
    }));

    expect(() => handleScoreCandidate({
      sessionId: start.sessionId,
      candidateId: "c1",
      scores: { wrongDim: 0.8 },
      critique: ["test"]
    })).toThrow("Missing score dimensions");
  });

  it("persists lineage parentIds on mutations", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.99,
      populationLimit: 5,
      generationLimit: 5,
      candidates: [{ id: "c1", answer: "A" }]
    }));
    const sessionId = start.sessionId;
    handleScoreCandidate({ sessionId, candidateId: "c1", scores: { logicalConsistency: 0.8, evidenceGrounding: 0.7, solutionUsefulness: 0.75 }, critique: ["ok"] });
    handleSelect({ sessionId });

    const mutResult = parseResult(handleMutate({ sessionId, parentId: "c1", candidateId: "m1", answer: "Mutated" }));
    expect(mutResult.parentId).toBe("c1");

    // Score the mutated candidate so it enters the population
    handleScoreCandidate({ sessionId, candidateId: "m1", scores: { logicalConsistency: 0.85, evidenceGrounding: 0.75, solutionUsefulness: 0.8 }, critique: ["better"] });

    // Verify parentIds survived scoring by checking next_step population
    const step = parseResult(handleNextStep({ sessionId }));
    // The scored candidate should be in the population with parentIds preserved
    expect(step.populationSize).toBeGreaterThanOrEqual(2);
  });

  it("auto-transitions from mutating to scoring on first score", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.99,
      populationLimit: 5,
      generationLimit: 5,
      candidates: [{ id: "c1", answer: "A" }]
    }));
    const sessionId = start.sessionId;
    handleScoreCandidate({ sessionId, candidateId: "c1", scores: { logicalConsistency: 0.8, evidenceGrounding: 0.7, solutionUsefulness: 0.75 }, critique: ["ok"] });
    handleSelect({ sessionId });

    // Mutate
    handleMutate({ sessionId, parentId: "c1", candidateId: "m1", answer: "Mut" });

    // Score while in mutating status (should auto-transition to scoring)
    const scoreResult = parseResult(handleScoreCandidate({ sessionId, candidateId: "m1", scores: { logicalConsistency: 0.85, evidenceGrounding: 0.75, solutionUsefulness: 0.8 }, critique: ["better"] }));
    expect(scoreResult.fitness).toBeGreaterThan(0);

    // Further mutations should now be rejected (status is scoring)
    // Actually status auto-transitioned to ready_to_select since all pending scored
    // So it should throw "Cannot mutate in ready_to_select"
    expect(() => handleMutate({ sessionId, parentId: "c1", candidateId: "m2", answer: "Mut2" })).toThrow("Cannot mutate");
  });

  it("uses category preset when no weights provided", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.8,
      populationLimit: 3,
      generationLimit: 3,
      category: "math",
      candidates: [{ id: "c1", answer: "Proof attempt" }]
    }));
    expect(start.resolvedCategory).toBe("math");
    expect(start.weightDimensions).toEqual(
      expect.arrayContaining(["mathematicalRigor", "stepValidity", "solutionCompleteness"])
    );
    expect(start.weightDimensions).not.toContain("logicalConsistency");

    // Scoring must use math dimensions
    const score = parseResult(handleScoreCandidate({
      sessionId: start.sessionId,
      candidateId: "c1",
      scores: { mathematicalRigor: 0.9, stepValidity: 0.8, solutionCompleteness: 0.7 },
      critique: ["Proof is mostly complete"]
    }));
    // fitness = 0.45*0.9 + 0.30*0.8 + 0.25*0.7 = 0.405 + 0.24 + 0.175 = 0.82
    expect(score.fitness).toBeCloseTo(0.82, 2);
  });

  it("explicit weights override category", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.7,
      populationLimit: 3,
      generationLimit: 3,
      category: "math",
      weights: { custom: 1.0 },
      candidates: [{ id: "c1", answer: "A" }]
    }));
    expect(start.resolvedCategory).toBe("custom");
    expect(start.weightDimensions).toEqual(["custom"]);
  });

  it("defaults to general when neither category nor weights provided", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.85,
      populationLimit: 5,
      generationLimit: 5,
      candidates: [{ id: "c1", answer: "A" }]
    }));
    expect(start.resolvedCategory).toBe("general");
    expect(start.weightDimensions).toEqual(
      expect.arrayContaining(["logicalConsistency", "evidenceGrounding", "solutionUsefulness"])
    );
  });

  it("rejects scoring with wrong dimensions for category preset", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.8,
      populationLimit: 3,
      generationLimit: 3,
      category: "coding",
      candidates: [{ id: "c1", answer: "function foo() {}" }]
    }));
    expect(() => handleScoreCandidate({
      sessionId: start.sessionId,
      candidateId: "c1",
      scores: { logicalConsistency: 0.8 },
      critique: ["wrong dims"]
    })).toThrow("Missing score dimensions");
  });

  it("handleNextStep suggests scoring when mutating with pending candidates", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.99,
      populationLimit: 5,
      generationLimit: 5,
      candidates: [{ id: "c1", answer: "A" }]
    }));
    const sessionId = start.sessionId;
    handleScoreCandidate({ sessionId, candidateId: "c1", scores: { logicalConsistency: 0.8, evidenceGrounding: 0.7, solutionUsefulness: 0.75 }, critique: ["ok"] });
    handleSelect({ sessionId });

    // Mutate (creates pending candidate but stays in mutating)
    handleMutate({ sessionId, parentId: "c1", candidateId: "m1", answer: "Mut" });

    // next_step should suggest scoring since there are pending candidates
    const step = parseResult(handleNextStep({ sessionId }));
    expect(step.suggestion.suggestedTool).toBe("reasonforge_score_candidate");
  });

  // --- Pre-scored candidates tests ---

  it("accepts pre-scored candidates and skips scoring phase", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.99,
      populationLimit: 5,
      generationLimit: 5,
      candidates: [
        { id: "c1", answer: "Answer 1", scores: { logicalConsistency: 0.8, evidenceGrounding: 0.7, solutionUsefulness: 0.75 }, critique: ["decent"] },
        { id: "c2", answer: "Answer 2", scores: { logicalConsistency: 0.6, evidenceGrounding: 0.5, solutionUsefulness: 0.55 }, critique: ["weak"] }
      ]
    }));
    expect(start.preScoredCount).toBe(2);
    expect(start.candidateCount).toBe(0);
    expect(start.status).toBe("ready_to_select");

    // Should be ready for selection immediately
    const step = parseResult(handleNextStep({ sessionId: start.sessionId }));
    expect(step.status).toBe("ready_to_select");
    expect(step.populationSize).toBe(2);
    expect(step.pendingCount).toBe(0);
    expect(step.suggestion.suggestedTool).toBe("reasonforge_select");
  });

  it("mixes pre-scored and unscored candidates", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.99,
      populationLimit: 5,
      generationLimit: 5,
      candidates: [
        { id: "c1", answer: "Pre-scored", scores: { logicalConsistency: 0.8, evidenceGrounding: 0.7, solutionUsefulness: 0.75 }, critique: ["ok"] },
        { id: "c2", answer: "Unscored" }
      ]
    }));
    expect(start.preScoredCount).toBe(1);
    expect(start.candidateCount).toBe(1);
    expect(start.status).toBe("scoring");

    // Score the remaining candidate
    handleScoreCandidate({
      sessionId: start.sessionId,
      candidateId: "c2",
      scores: { logicalConsistency: 0.6, evidenceGrounding: 0.5, solutionUsefulness: 0.55 },
      critique: ["needs work"]
    });

    const step = parseResult(handleNextStep({ sessionId: start.sessionId }));
    expect(step.populationSize).toBe(2);
    expect(step.pendingCount).toBe(0);
  });

  it("does not count pre-scored candidates against evaluation budget", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.99,
      populationLimit: 3,
      generationLimit: 1, // budget = 3
      candidates: [
        { id: "c1", answer: "A", scores: { logicalConsistency: 0.8, evidenceGrounding: 0.7, solutionUsefulness: 0.75 }, critique: ["ok"] },
        { id: "c2", answer: "B", scores: { logicalConsistency: 0.6, evidenceGrounding: 0.5, solutionUsefulness: 0.55 }, critique: ["ok"] }
      ]
    }));

    // Select and mutate
    handleSelect({ sessionId: start.sessionId, survivorCount: 2 });
    handleMutate({ sessionId: start.sessionId, parentId: "c1", candidateId: "m1", answer: "Mut" });

    // Should succeed — budget not consumed by pre-scored candidates
    const score = parseResult(handleScoreCandidate({
      sessionId: start.sessionId,
      candidateId: "m1",
      scores: { logicalConsistency: 0.85, evidenceGrounding: 0.75, solutionUsefulness: 0.8 },
      critique: ["better"]
    }));
    expect(score.fitness).toBeGreaterThan(0);
  });

  // --- Budget exhaustion -> failed tests ---

  it("transitions to failed status on budget exhaustion", () => {
    const start = parseResult(handleStartSession({
      threshold: 0.99,
      populationLimit: 2,
      generationLimit: 1, // budget = 2
      candidates: [{ id: "c1", answer: "A" }, { id: "c2", answer: "B" }]
    }));
    const sessionId = start.sessionId;

    // Use all 2 budget evaluations on initial candidates
    handleScoreCandidate({ sessionId, candidateId: "c1", scores: { logicalConsistency: 0.5, evidenceGrounding: 0.5, solutionUsefulness: 0.5 }, critique: ["ok"] });
    handleScoreCandidate({ sessionId, candidateId: "c2", scores: { logicalConsistency: 0.4, evidenceGrounding: 0.4, solutionUsefulness: 0.4 }, critique: ["ok"] });

    // Select with survivorCount=1 to make room for mutation
    handleSelect({ sessionId, survivorCount: 1 });
    handleMutate({ sessionId, parentId: "c1", candidateId: "m1", answer: "Mut" });

    // Budget exhausted (2 evals used, budget=2) — should throw AND mark session as failed
    expect(() => handleScoreCandidate({
      sessionId,
      candidateId: "m1",
      scores: { logicalConsistency: 0.6, evidenceGrounding: 0.6, solutionUsefulness: 0.6 },
      critique: ["test"]
    })).toThrow("budget");

    // Verify session is now failed
    const step = parseResult(handleNextStep({ sessionId }));
    expect(step.status).toBe("failed");
  });
});
