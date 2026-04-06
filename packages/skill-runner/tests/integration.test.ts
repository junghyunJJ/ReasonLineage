import { describe, it, expect, afterEach } from "vitest";
import {
  handleInit,
  handleScore,
  handleSelect,
  handleMutate,
  handleNextStep,
  deleteSessionFile
} from "../src/index.js";

/**
 * End-to-end integration test simulating the full Skill flow:
 * init → score×3 → next-step → select → mutate → score → next-step → verify → cleanup
 *
 * No LLM involved — all answers and scores are hardcoded.
 */
describe("full evolution lifecycle", () => {
  let sessionId: string;

  afterEach(() => {
    if (sessionId) deleteSessionFile(sessionId);
  });

  it("completes a full evolution cycle: init → score → select → mutate → score → completed", () => {
    // Step 1: Init with 3 candidates
    const init = handleInit({
      threshold: 0.85,
      populationLimit: 5,
      generationLimit: 3,
      candidates: [
        { id: "seed-1", answer: "Walk there because it is only 50 meters away." },
        { id: "seed-2", answer: "Drive because the car must be at the car wash." },
        { id: "seed-3", answer: "Either could work depending on context." }
      ]
    });
    sessionId = init.sessionId;
    expect(init.candidateCount).toBe(3);

    // Step 2: Score candidate seed-1 (weak — misses constraint)
    const s1 = handleScore({
      sessionId,
      candidateId: "seed-1",
      scores: { logicalConsistency: 0.3, evidenceGrounding: 0.4, solutionUsefulness: 0.2 },
      critique: ["Misses that the car must be physically present at the car wash."]
    });
    expect(s1.fitness).toBeCloseTo(0.29, 2);
    expect(s1.totalPending).toBe(2);

    // Step 3: Score candidate seed-2 (good but not above threshold)
    const s2 = handleScore({
      sessionId,
      candidateId: "seed-2",
      scores: { logicalConsistency: 0.8, evidenceGrounding: 0.7, solutionUsefulness: 0.8 },
      critique: ["Correct reasoning but could be more specific about why distance is irrelevant."]
    });
    expect(s2.fitness).toBeCloseTo(0.78, 2);
    expect(s2.totalPending).toBe(1);

    // Step 4: Score candidate seed-3 (mediocre)
    const s3 = handleScore({
      sessionId,
      candidateId: "seed-3",
      scores: { logicalConsistency: 0.4, evidenceGrounding: 0.3, solutionUsefulness: 0.4 },
      critique: ["Indecisive. Does not identify the core constraint."]
    });
    expect(s3.fitness).toBeCloseTo(0.38, 2);
    expect(s3.totalPending).toBe(0);

    // Step 5: Check status — should be ready_to_select (no candidate hit 0.85)
    const status1 = handleNextStep({ sessionId });
    expect(status1.status).toBe("ready_to_select");
    expect(status1.bestCandidateId).toBe("seed-2");
    expect(status1.suggestion.suggestedAction).toBe("select");

    // Step 6: Select top 2 survivors
    const sel = handleSelect({ sessionId, survivorCount: 2 });
    expect(sel.generation).toBe(1);
    expect(sel.survivors).toHaveLength(2);
    expect(sel.survivors[0].id).toBe("seed-2");
    expect(sel.eliminated).toHaveLength(1);
    expect(sel.eliminated[0].id).toBe("seed-1");

    // Step 7: Mutate the best candidate (seed-2)
    const mut = handleMutate({
      sessionId,
      parentId: "seed-2",
      candidateId: "mut-gen-1",
      answer: "Drive. The car wash requires the car to be physically present. Walking 50 meters would leave your car behind, making the trip pointless. The distance is a red herring — you must drive regardless."
    });
    expect(mut.candidateId).toBe("mut-gen-1");
    expect(mut.parentId).toBe("seed-2");

    // Step 8: Score the mutation (should exceed threshold)
    const sm = handleScore({
      sessionId,
      candidateId: "mut-gen-1",
      scores: { logicalConsistency: 0.95, evidenceGrounding: 0.85, solutionUsefulness: 0.92 },
      critique: ["Excellent. Identifies the core constraint and the red herring."]
    });
    // 0.95*0.5 + 0.85*0.2 + 0.92*0.3 = 0.475 + 0.17 + 0.276 = 0.921
    expect(sm.fitness).toBeCloseTo(0.921, 2);

    // Step 9: Check final status — should be completed (threshold met)
    const status2 = handleNextStep({ sessionId });
    expect(status2.status).toBe("completed");
    expect(status2.thresholdMet).toBe(true);
    expect(status2.bestCandidateId).toBe("mut-gen-1");
    expect(status2.bestFitness).toBeGreaterThanOrEqual(0.85);
    expect(status2.generation).toBe(1);
    expect(status2.suggestion.suggestedAction).toBeNull();

    // Step 10: Verify the best answer content
    expect(status2.bestAnswer).toContain("Drive");
    expect(status2.bestAnswer).toContain("red herring");

    // Step 11: Cleanup
    const deleted = deleteSessionFile(sessionId);
    expect(deleted).toBe(true);
    sessionId = ""; // prevent double-delete in afterEach
  });
});
