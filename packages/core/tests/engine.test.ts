import { describe, expect, it } from "vitest";

import {
  createCandidate,
  runReasonForgeCycle,
  type CandidateJudgeResult
} from "../src/index";

describe("runReasonForgeCycle", () => {
  it("converges to drive for the seeded car-wash benchmark and emits step events", async () => {
    const seeds = [
      createCandidate("seed-walk", "Walk there because it is only 50 meters."),
      createCandidate("seed-hesitate", "Either walk or drive could work."),
      createCandidate("seed-drive", "Drive there because you need the car at the wash.")
    ];

    const judgeTable = new Map<string, CandidateJudgeResult>([
      [
        "seed-walk",
        {
          logicalConsistency: 0.8,
          evidenceGrounding: 0.4,
          solutionUsefulness: 0.1
        }
      ],
      [
        "seed-hesitate",
        {
          logicalConsistency: 0.7,
          evidenceGrounding: 0.4,
          solutionUsefulness: 0.3
        }
      ],
      [
        "seed-drive",
        {
          logicalConsistency: 0.92,
          evidenceGrounding: 0.8,
          solutionUsefulness: 0.95
        }
      ],
      [
        "mutated-drive",
        {
          logicalConsistency: 0.96,
          evidenceGrounding: 0.82,
          solutionUsefulness: 0.97
        }
      ]
    ]);

    const result = await runReasonForgeCycle({
      populationLimit: 5,
      generationLimit: 5,
      threshold: 0.85,
      initialPopulation: seeds,
      judge: async (candidate) => judgeTable.get(candidate.id)!,
      critique: async (candidate) =>
        candidate.answer.includes("Walk")
          ? ["This ignores that the car must be taken to the wash."]
          : ["Reasoning aligns with taking the car to the car wash."],
      mutate: async (candidate) =>
        candidate.id === "seed-drive"
          ? createCandidate(
              "mutated-drive",
              "Drive the car to the wash because the car itself must be brought there."
            )
          : createCandidate(
              `${candidate.id}-retry`,
              `${candidate.answer} Reconsider the transport requirement.`
            ),
      crossover: async (left, right) =>
        createCandidate(
          `${left.id}+${right.id}`,
          `${left.answer} ${right.answer}`.trim()
        )
    });

    expect(result.status).toBe("threshold_met");
    expect(result.finalAnswer.toLowerCase()).toContain("drive");
    expect(result.finalFitness).toBeGreaterThanOrEqual(0.85);
    expect(result.events.map((event) => event.type)).toEqual(
      expect.arrayContaining([
        "run.started",
        "candidate.scored",
        "mutation.applied",
        "selection.completed",
        "threshold.reached"
      ])
    );
  });

  it("streams events through an event callback as the cycle progresses", async () => {
    const seen: string[] = [];

    await runReasonForgeCycle({
      populationLimit: 2,
      generationLimit: 1,
      threshold: 0.85,
      initialPopulation: [
        createCandidate("seed-drive", "Drive there because the car needs to be washed.")
      ],
      judge: async () => ({
        logicalConsistency: 0.9,
        evidenceGrounding: 0.9,
        solutionUsefulness: 0.95
      }),
      critique: async () => ["Looks good."],
      mutate: async () =>
        createCandidate("seed-drive-2", "Drive the car to the wash and return home."),
      onEvent: (event) => {
        seen.push(event.type);
      }
    });

    expect(seen).toContain("run.started");
    expect(seen).toContain("mutation.applied");
    expect(seen.at(-1)).toBe("run.completed");
  });
});
