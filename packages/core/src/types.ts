export type JudgeWeights = {
  logicalConsistency: number;
  evidenceGrounding: number;
  solutionUsefulness: number;
};

export type CandidateJudgeResult = {
  logicalConsistency: number;
  evidenceGrounding: number;
  solutionUsefulness: number;
};

export type BenchmarkCase = {
  id: string;
  label: string;
  prompt: string;
  expectedAnswer: string;
};

export type BenchmarkVerdict = {
  passed: boolean;
  expectedAnswer: string;
  normalizedAnswer: string;
};

export type Candidate = {
  id: string;
  answer: string;
};

export type ScoredCandidate = Candidate &
  CandidateJudgeResult & {
    fitness: number;
    critique: string[];
    benchmarkVerdict: BenchmarkVerdict;
  };

export type EvolutionEvent =
  | {
      type: "run.started";
      generation: number;
      populationSize: number;
    }
  | {
      type: "candidate.scored";
      generation: number;
      candidateId: string;
      answer: string;
      fitness: number;
      logicalConsistency: number;
      evidenceGrounding: number;
      solutionUsefulness: number;
      critique: string[];
      benchmarkPassed: boolean;
    }
  | {
      type: "selection.completed";
      generation: number;
      survivorIds: string[];
    }
  | {
      type: "mutation.applied";
      generation: number;
      parentId: string;
      candidateId: string;
    }
  | {
      type: "crossover.applied";
      generation: number;
      parentIds: [string, string];
      candidateId: string;
    }
  | {
      type: "threshold.reached";
      generation: number;
      candidateId: string;
      fitness: number;
    }
  | {
      type: "run.completed";
      generation: number;
      status: RunStatus;
      candidateId: string;
      fitness: number;
    };

export type RunStatus = "threshold_met" | "human_review_required";

export type RunReasonForgeCycleInput = {
  populationLimit: number;
  generationLimit: number;
  threshold: number;
  benchmark?: BenchmarkCase;
  deferThresholdUntilAfterMutation?: boolean;
  initialPopulation: Candidate[];
  judge: (candidate: Candidate) => Promise<CandidateJudgeResult>;
  critique: (candidate: Candidate) => Promise<string[]>;
  mutate: (candidate: Candidate) => Promise<Candidate>;
  crossover?: (left: Candidate, right: Candidate) => Promise<Candidate>;
  onEvent?: (event: EvolutionEvent) => void | Promise<void>;
};

export type RunReasonForgeCycleResult = {
  status: RunStatus;
  finalAnswer: string;
  finalFitness: number;
  finalCandidate: ScoredCandidate;
  events: EvolutionEvent[];
};
