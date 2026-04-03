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
    expect(result.finalCandidate.scores).toBeDefined();
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

  it("strategy.survivorCount limits survivors to 1", async () => {
    const result = await runReasonForgeCycle({
      populationLimit: 5,
      generationLimit: 1,
      threshold: 0.99,
      initialPopulation: [
        createCandidate("a", "Answer A"),
        createCandidate("b", "Answer B"),
        createCandidate("c", "Answer C")
      ],
      judge: async (candidate) => ({
        logicalConsistency: candidate.id === "a" ? 0.9 : 0.5,
        evidenceGrounding: 0.5,
        solutionUsefulness: 0.5
      }),
      critique: async () => [],
      mutate: async (candidate) =>
        createCandidate(`${candidate.id}-mut`, `${candidate.answer} mutated`),
      strategy: { survivorCount: 1 }
    });

    const selectionEvents = result.events.filter(
      (e) => e.type === "selection.completed"
    ) as Extract<(typeof result.events)[number], { type: "selection.completed" }>[];
    expect(selectionEvents.length).toBeGreaterThan(0);
    for (const event of selectionEvents) {
      expect(event.survivorIds).toHaveLength(1);
    }
  });

  it("strategy.mutationsPerTarget=2 emits 2 mutation.applied events per generation", async () => {
    const result = await runReasonForgeCycle({
      populationLimit: 10,
      generationLimit: 1,
      threshold: 0.99,
      initialPopulation: [createCandidate("seed", "Initial answer")],
      judge: async () => ({
        logicalConsistency: 0.5,
        evidenceGrounding: 0.5,
        solutionUsefulness: 0.5
      }),
      critique: async () => [],
      mutate: async (candidate) =>
        createCandidate(`${candidate.id}-${Date.now()}-${Math.random()}`, `${candidate.answer} v`),
      strategy: { mutationsPerTarget: 2 }
    });

    const mutationEvents = result.events.filter((e) => e.type === "mutation.applied");
    // generationLimit=1, mutationTarget="best"(1 target), mutationsPerTarget=2 → 2 mutations
    expect(mutationEvents).toHaveLength(2);
  });

  it("strategy.crossoverPolicy=never skips crossover even with multiple survivors", async () => {
    let crossoverCalled = false;
    const result = await runReasonForgeCycle({
      populationLimit: 5,
      generationLimit: 1,
      threshold: 0.99,
      initialPopulation: [
        createCandidate("x", "Answer X"),
        createCandidate("y", "Answer Y")
      ],
      judge: async () => ({
        logicalConsistency: 0.5,
        evidenceGrounding: 0.5,
        solutionUsefulness: 0.5
      }),
      critique: async () => [],
      mutate: async (candidate) =>
        createCandidate(`${candidate.id}-mut`, `${candidate.answer} mutated`),
      crossover: async (left, right) => {
        crossoverCalled = true;
        return createCandidate(`${left.id}+${right.id}`, `${left.answer} ${right.answer}`);
      },
      strategy: { crossoverPolicy: "never" }
    });

    expect(crossoverCalled).toBe(false);
    const crossoverEvents = result.events.filter((e) => e.type === "crossover.applied");
    expect(crossoverEvents).toHaveLength(0);
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

  it("termination.requireBenchmarkPass=false terminates on fitness alone", async () => {
    // No benchmark provided but fitness will be high — without requireBenchmarkPass=false
    // the default benchmark would fail (answer doesn't contain "drive"), blocking termination.
    const result = await runReasonForgeCycle({
      populationLimit: 3,
      generationLimit: 5,
      threshold: 0.85,
      initialPopulation: [
        createCandidate("a", "The answer is yes.")
      ],
      judge: async () => ({
        logicalConsistency: 0.9,
        evidenceGrounding: 0.9,
        solutionUsefulness: 0.95
      }),
      critique: async () => [],
      mutate: async (candidate) =>
        createCandidate(`${candidate.id}-mut`, `${candidate.answer} updated`),
      strategy: { termination: { requireBenchmarkPass: false } }
    });

    expect(result.status).toBe("threshold_met");
  });

  it("selection.sortBy=fitness-asc changes sort order", async () => {
    // With fitness-asc the worst candidates bubble to the top and become survivors/mutationTargets,
    // so the result will differ from the default fitness-desc run.
    const defaultResult = await runReasonForgeCycle({
      populationLimit: 3,
      generationLimit: 2,
      threshold: 0.99,
      initialPopulation: [
        createCandidate("hi", "High fitness answer"),
        createCandidate("lo", "Low fitness answer")
      ],
      judge: async (candidate) => ({
        logicalConsistency: candidate.id === "hi" ? 0.9 : 0.1,
        evidenceGrounding: candidate.id === "hi" ? 0.9 : 0.1,
        solutionUsefulness: candidate.id === "hi" ? 0.9 : 0.1
      }),
      critique: async () => [],
      mutate: async (candidate) =>
        createCandidate(`${candidate.id}-mut`, `${candidate.answer} mutated`)
    });

    const ascResult = await runReasonForgeCycle({
      populationLimit: 3,
      generationLimit: 2,
      threshold: 0.99,
      initialPopulation: [
        createCandidate("hi", "High fitness answer"),
        createCandidate("lo", "Low fitness answer")
      ],
      judge: async (candidate) => ({
        logicalConsistency: candidate.id === "hi" ? 0.9 : 0.1,
        evidenceGrounding: candidate.id === "hi" ? 0.9 : 0.1,
        solutionUsefulness: candidate.id === "hi" ? 0.9 : 0.1
      }),
      critique: async () => [],
      mutate: async (candidate) =>
        createCandidate(`${candidate.id}-mut`, `${candidate.answer} mutated`),
      strategy: { selection: { sortBy: "fitness-asc" } }
    });

    // The two runs should produce different final candidates because sort order differs
    expect(ascResult.finalCandidate.id).not.toBe(defaultResult.finalCandidate.id);
  });

  it("computes finite fitness with custom-only dimensions", async () => {
    const customWeights = { creativity: 0.4, efficiency: 0.3, clarity: 0.3 };
    const judgeResult = { creativity: 0.8, efficiency: 0.9, clarity: 0.7, logicalConsistency: 0, evidenceGrounding: 0, solutionUsefulness: 0 };

    const result = await runReasonForgeCycle({
      populationLimit: 3,
      generationLimit: 1,
      threshold: 0.5,
      initialPopulation: [
        createCandidate("a", "Answer A"),
        createCandidate("b", "Answer B")
      ],
      judge: async () => judgeResult,
      critique: async () => ["test critique"],
      mutate: async (c) => createCandidate(`${c.id}-m`, `Mutated ${c.answer}`),
      crossover: async (l, r) => createCandidate(`${l.id}+${r.id}`, "Crossed"),
      strategy: {
        weights: customWeights as any
      }
    });

    expect(result.finalFitness).toBeGreaterThan(0);
    expect(Number.isFinite(result.finalFitness)).toBe(true);
    // Expected: 0.4*0.8 + 0.3*0.9 + 0.3*0.7 = 0.32 + 0.27 + 0.21 = 0.80
    expect(result.finalFitness).toBeCloseTo(0.80);
  });
});
