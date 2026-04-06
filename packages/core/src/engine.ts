import { evaluateBenchmarkAnswer, getDefaultBenchmarkCase } from "./benchmark.js";
import { calculateFitness, defaultJudgeWeights } from "./scoring.js";
import type {
  Candidate,
  EvolutionEvent,
  EvolutionStrategy,
  RunReasonForgeCycleInput,
  RunReasonForgeCycleResult,
  ScoredCandidate
} from "./types.js";

function sortByFitness(population: ScoredCandidate[]) {
  return [...population].sort((left, right) => right.fitness - left.fitness);
}

function sortPopulation(population: ScoredCandidate[], strategy?: EvolutionStrategy): ScoredCandidate[] {
  const sortBy = strategy?.selection?.sortBy ?? "fitness-desc";
  if (sortBy === "fitness-desc") {
    return sortByFitness(population);
  }
  if (sortBy === "fitness-asc") {
    return [...population].sort((a, b) => a.fitness - b.fitness);
  }
  return [...population].sort(sortBy);
}

function shouldTerminate(best: ScoredCandidate, input: RunReasonForgeCycleInput): boolean {
  const termination = input.strategy?.termination;
  const useFitness = termination?.useFitnessThreshold ?? true;
  const requireBenchmark = termination?.requireBenchmarkPass ?? !!input.benchmark;

  let met = true;
  if (useFitness) {
    met = met && best.fitness >= input.threshold;
  }
  if (requireBenchmark) {
    met = met && best.benchmarkVerdict.passed;
  }
  if (termination?.custom) {
    met = met && termination.custom(best);
  }
  return met;
}

async function publishEvent(
  event: EvolutionEvent,
  events: EvolutionEvent[],
  input: RunReasonForgeCycleInput
) {
  events.push(event);
  await input.onEvent?.(event);
}

async function scoreCandidate(
  candidate: Candidate,
  generation: number,
  input: RunReasonForgeCycleInput,
  events: EvolutionEvent[]
): Promise<ScoredCandidate> {
  const benchmark = input.benchmark ?? getDefaultBenchmarkCase();
  const critique = await input.critique(candidate);
  const scores = await input.judge(candidate);
  const fitness = calculateFitness(input.strategy?.weights ?? defaultJudgeWeights, { ...scores } as Record<string, number>);
  const benchmarkVerdict = evaluateBenchmarkAnswer(benchmark, candidate.answer);

  await publishEvent(
    {
      type: "candidate.scored",
      generation,
      candidateId: candidate.id,
      answer: candidate.answer,
      fitness,
      logicalConsistency: scores.logicalConsistency,
      evidenceGrounding: scores.evidenceGrounding,
      solutionUsefulness: scores.solutionUsefulness,
      scores: { ...scores } as Record<string, number>,
      critique,
      benchmarkPassed: benchmarkVerdict.passed
    },
    events,
    input
  );

  return {
    ...candidate,
    ...scores,
    critique,
    fitness,
    benchmarkVerdict,
    scores: { ...scores } as Record<string, number>
  } satisfies ScoredCandidate;
}

function pickBest(population: ScoredCandidate[]) {
  return sortByFitness(population)[0];
}

export function createCandidate(id: string, answer: string, parentIds?: string[]): Candidate {
  return parentIds ? { id, answer, parentIds } : { id, answer };
}

export async function runReasonForgeCycle(
  input: RunReasonForgeCycleInput
): Promise<RunReasonForgeCycleResult> {
  const events: EvolutionEvent[] = [];
  await publishEvent(
    {
      type: "run.started",
      generation: 0,
      populationSize: input.initialPopulation.slice(0, input.populationLimit).length
    },
    events,
    input
  );

  const initialPopulation = input.initialPopulation.slice(0, input.populationLimit);
  let population: ScoredCandidate[] = await Promise.all(
    initialPopulation.map((candidate) => scoreCandidate(candidate, 0, input, events))
  );

  let best = pickBest(population);

  for (let generation = 1; generation <= input.generationLimit; generation += 1) {
    const survivorCount = input.strategy?.survivorCount ?? 2;
    const survivors = sortPopulation(population, input.strategy).slice(0, Math.min(survivorCount, population.length));
    await publishEvent(
      {
        type: "selection.completed",
        generation,
        survivorIds: survivors.map((candidate) => candidate.id)
      },
      events,
      input
    );

    const nextPopulation = [...survivors];
    if (
      input.deferThresholdUntilAfterMutation === false &&
      shouldTerminate(best, input)
    ) {
      await publishEvent(
        {
          type: "threshold.reached",
          generation,
          candidateId: best.id,
          fitness: best.fitness
        },
        events,
        input
      );
      await publishEvent(
        {
          type: "run.completed",
          generation,
          status: "threshold_met",
          candidateId: best.id,
          fitness: best.fitness
        },
        events,
        input
      );

      return {
        status: "threshold_met",
        finalAnswer: best.answer,
        finalFitness: best.fitness,
        finalCandidate: best,
        events
      };
    }

    const mutationTarget = input.strategy?.mutationTarget ?? "best";
    const mutationsPerTarget = input.strategy?.mutationsPerTarget ?? 1;

    let mutationTargets: ScoredCandidate[];
    if (mutationTarget === "best") {
      mutationTargets = [best];
    } else if (mutationTarget === "random") {
      mutationTargets = [survivors[Math.floor(Math.random() * survivors.length)]];
    } else {
      mutationTargets = survivors;
    }

    for (const target of mutationTargets) {
      for (let m = 0; m < mutationsPerTarget; m += 1) {
        const mutated = await input.mutate(target);
        await publishEvent(
          {
            type: "mutation.applied",
            generation,
            parentId: target.id,
            candidateId: mutated.id
          },
          events,
          input
        );
        nextPopulation.push(await scoreCandidate(mutated, generation, input, events));
      }
    }

    const crossoverPolicy = input.strategy?.crossoverPolicy ?? "when-below-threshold";
    const crossoverAllowed =
      crossoverPolicy === "never"
        ? false
        : crossoverPolicy === "always"
          ? true
          : !shouldTerminate(best, input);

    if (input.crossover && survivors.length > 1 && crossoverAllowed) {
      const crossed = await input.crossover(survivors[0], survivors[1]);
      await publishEvent(
        {
          type: "crossover.applied",
          generation,
          parentIds: [survivors[0].id, survivors[1].id],
          candidateId: crossed.id
        },
        events,
        input
      );
      nextPopulation.push(await scoreCandidate(crossed, generation, input, events));
    }

    population = sortPopulation(nextPopulation, input.strategy).slice(0, input.populationLimit);
    best = pickBest(population);

    if (shouldTerminate(best, input)) {
      await publishEvent(
        {
          type: "threshold.reached",
          generation,
          candidateId: best.id,
          fitness: best.fitness
        },
        events,
        input
      );
      await publishEvent(
        {
          type: "run.completed",
          generation,
          status: "threshold_met",
          candidateId: best.id,
          fitness: best.fitness
        },
        events,
        input
      );

      return {
        status: "threshold_met",
        finalAnswer: best.answer,
        finalFitness: best.fitness,
        finalCandidate: best,
        events
      };
    }
  }

  await publishEvent(
    {
      type: "run.completed",
      generation: input.generationLimit,
      status: "human_review_required",
      candidateId: best.id,
      fitness: best.fitness
    },
    events,
    input
  );

  return {
    status: "human_review_required",
    finalAnswer: best.answer,
    finalFitness: best.fitness,
    finalCandidate: best,
    events
  };
}
