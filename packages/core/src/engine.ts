import { evaluateBenchmarkAnswer, getDefaultBenchmarkCase } from "./benchmark";
import { calculateFitness } from "./scoring";
import type {
  Candidate,
  EvolutionEvent,
  RunReasonForgeCycleInput,
  RunReasonForgeCycleResult,
  ScoredCandidate
} from "./types";

function sortByFitness(population: ScoredCandidate[]) {
  return [...population].sort((left, right) => right.fitness - left.fitness);
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
) {
  const benchmark = input.benchmark ?? getDefaultBenchmarkCase();
  const critique = await input.critique(candidate);
  const scores = await input.judge(candidate);
  const fitness = calculateFitness(scores);
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
    benchmarkVerdict
  } satisfies ScoredCandidate;
}

function pickBest(population: ScoredCandidate[]) {
  return sortByFitness(population)[0];
}

export function createCandidate(id: string, answer: string): Candidate {
  return { id, answer };
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
  let population = await Promise.all(
    initialPopulation.map((candidate) => scoreCandidate(candidate, 0, input, events))
  );

  let best = pickBest(population);

  for (let generation = 1; generation <= input.generationLimit; generation += 1) {
    const survivors = sortByFitness(population).slice(0, Math.min(2, population.length));
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
      best.fitness >= input.threshold &&
      best.benchmarkVerdict.passed
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

    const mutated = await input.mutate(best);
    await publishEvent(
      {
        type: "mutation.applied",
        generation,
        parentId: best.id,
        candidateId: mutated.id
      },
      events,
      input
    );
    nextPopulation.push(await scoreCandidate(mutated, generation, input, events));

    if (
      input.crossover &&
      survivors.length > 1 &&
      !(best.fitness >= input.threshold && best.benchmarkVerdict.passed)
    ) {
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

    population = sortByFitness(nextPopulation).slice(0, input.populationLimit);
    best = pickBest(population);

    if (best.fitness >= input.threshold && best.benchmarkVerdict.passed) {
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
