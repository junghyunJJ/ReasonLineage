export const DEFAULT_JUDGE_DIMENSIONS = [
  "logicalConsistency",
  "evidenceGrounding",
  "solutionUsefulness"
] as const;
export type DefaultJudgeDimension = typeof DEFAULT_JUDGE_DIMENSIONS[number];

export type JudgeWeights = {
  logicalConsistency: number;
  evidenceGrounding: number;
  solutionUsefulness: number;
  [dimension: string]: number;
};

export type CandidateJudgeResult = {
  logicalConsistency: number;
  evidenceGrounding: number;
  solutionUsefulness: number;
  [dimension: string]: number;
};

export type BenchmarkCase = {
  id: string;
  label: string;
  prompt: string;
  expectedAnswer: string;
  matcher?: (expected: string, answer: string) => boolean;
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

export type ScoredCandidate = Candidate & {
  logicalConsistency: number;
  evidenceGrounding: number;
  solutionUsefulness: number;
  fitness: number;
  critique: string[];
  benchmarkVerdict: BenchmarkVerdict;
  scores?: Record<string, number>;
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
      scores?: Record<string, number>;
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

export type TerminationCondition = {
  /** 피트니스 종료 조건 사용 여부 (기본값: true) */
  useFitnessThreshold?: boolean;
  /** 벤치마크 통과 필수 여부 (기본값: true) */
  requireBenchmarkPass?: boolean;
  /** 커스텀 종료 판단 함수 (제공시 기본 조건과 AND 결합) */
  custom?: (candidate: ScoredCandidate) => boolean;
};

export type SelectionStrategy = {
  /** 정렬 기준 (기본값: "fitness-desc") */
  sortBy?: "fitness-desc" | "fitness-asc" | ((a: ScoredCandidate, b: ScoredCandidate) => number);
};

export type EvolutionStrategy = {
  /** 각 세대에서 선택할 생존자 수 (기본값: 2) */
  survivorCount?: number;
  /** 변이 대상 선택 방식 (기본값: "best") */
  mutationTarget?: "best" | "random" | "all-survivors";
  /** 변이당 생성할 후보 수 (기본값: 1) */
  mutationsPerTarget?: number;
  /** 교차 실행 조건 (기본값: "when-below-threshold") */
  crossoverPolicy?: "always" | "when-below-threshold" | "never";
  /** 피트니스 가중치 오버라이드 (기본값: DEFAULT_JUDGE_WEIGHTS) */
  weights?: JudgeWeights;
  termination?: TerminationCondition;
  selection?: SelectionStrategy;
};

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
  strategy?: EvolutionStrategy;
};

export type RunReasonForgeCycleResult = {
  status: RunStatus;
  finalAnswer: string;
  finalFitness: number;
  finalCandidate: ScoredCandidate;
  events: EvolutionEvent[];
};
