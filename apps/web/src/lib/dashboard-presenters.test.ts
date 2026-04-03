import { describe, expect, it } from "vitest";

import type { CandidateCard, PublicRunEvent } from "./types";
import {
  formatDimensionName,
  getGenerationPanelNote,
  getLatestEventSequence,
  getLatestScoredGeneration,
  getSortedEvents,
  summarizeEventPayload
} from "./dashboard-presenters";

describe("dashboard presenters", () => {
  const events: PublicRunEvent[] = [
    {
      sequence: 14,
      type: "comparison.completed",
      payload: {
        runId: "run-123",
        status: "completed"
      },
      createdAt: "2026-03-28T00:00:00.000Z"
    },
    {
      sequence: 12,
      type: "reasonforge.thresholdReached",
      payload: {
        type: "threshold.reached",
        generation: 1,
        candidateId: "seed-drive",
        fitness: 1
      },
      createdAt: "2026-03-28T00:00:00.000Z"
    },
    {
      sequence: 13,
      type: "mode.completed",
      payload: {
        mode: "reasonforge",
        finalAnswer: "Drive the car there because the car itself must arrive at the wash.",
        finalFitness: 1
      },
      createdAt: "2026-03-28T00:00:00.000Z"
    }
  ];

  it("sorts live events from oldest to newest by sequence", () => {
    expect(getSortedEvents(events).map((event) => event.sequence)).toEqual([12, 13, 14]);
  });

  it("returns the newest sequence without reversing the source list", () => {
    expect(getLatestEventSequence(events)).toBe(14);
  });

  it("condenses known payload fields into a readable summary", () => {
    expect(
      summarizeEventPayload({
        mode: "reasonforge",
        finalAnswer: "Drive the car there because the car itself must arrive at the wash.",
        finalFitness: 1
      })
    ).toBe(
      "mode=reasonforge | answer=Drive the car there because the car itself must arrive at the wash. | fitness=1"
    );
  });

  it("falls back to compact key-value pairs for generic payloads", () => {
    expect(
      summarizeEventPayload({
        runId: "run-123",
        status: "completed"
      })
    ).toBe("runId=run-123 | status=completed");
  });

  it("reports the latest scored generation from candidate cards", () => {
    const candidates: Record<string, CandidateCard> = {
      "seed-drive": {
        id: "seed-drive",
        answer: "Drive the car there because the car itself must arrive at the car wash.",
        generation: 0,
        fitness: 1,
        logicalConsistency: 1,
        evidenceGrounding: 1,
        solutionUsefulness: 1,
        critique: [],
        benchmarkPassed: true,
        parents: [],
        source: "seed",
        selected: true
      }
    };

    expect(getLatestScoredGeneration(candidates)).toBe(0);
  });

  it("explains when the lifecycle advanced beyond the last scored generation", () => {
    const candidates: Record<string, CandidateCard> = {
      "seed-drive": {
        id: "seed-drive",
        answer: "Drive the car there because the car itself must arrive at the car wash.",
        generation: 0,
        fitness: 1,
        logicalConsistency: 1,
        evidenceGrounding: 1,
        solutionUsefulness: 1,
        critique: [],
        benchmarkPassed: true,
        parents: [],
        source: "seed",
        selected: true
      }
    };

    expect(getGenerationPanelNote(events, candidates)).toBe(
      "Threshold reached at Gen 1 before Gen 1 candidates were scored, so this panel currently stops at Gen 0."
    );
  });
});

describe("formatDimensionName", () => {
  it("converts camelCase to title case with spaces", () => {
    expect(formatDimensionName("logicalConsistency")).toBe("Logical Consistency");
  });

  it("handles single word", () => {
    expect(formatDimensionName("creativity")).toBe("Creativity");
  });

  it("handles multi-word camelCase", () => {
    expect(formatDimensionName("evidenceGrounding")).toBe("Evidence Grounding");
    expect(formatDimensionName("solutionUsefulness")).toBe("Solution Usefulness");
  });
});
