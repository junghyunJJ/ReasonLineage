# ReasonForge 진화 엔진 유연화 구현 계획 v2

**생성일:** 2026-04-02
**v2 수정일:** 2026-04-02
**상태:** 사용자 확인 대기
**복잡도:** HIGH
**범위:** packages/core (5파일), apps/web (6파일), 테스트 (4파일)

---

## RALPLAN-DR 요약

### 설계 원칙 (Principles)

1. **Additive-Only 확장**: 기존 명시적 필드를 삭제하지 않고, 새 필드를 추가하여 확장한다. 하위 호환성 100% 보존.
2. **Core 순수성 유지**: `packages/core`는 외부 의존성 없이 순수 로직만 담당. LLM 판단 위임은 orchestrator 레이어에서.
3. **점진적 마이그레이션**: 각 Phase가 독립적으로 배포 가능하며, 이전 Phase의 타입을 깨뜨리지 않는다.
4. **LLM 위임 범위 제한**: LLM에게는 "무엇을 평가할지"(차원, 가중치, 프롬프트)만 위임. "어떻게 진화시킬지"(survivorCount, threshold 등)는 기본값 유지.
5. **데모 경험 보존**: 벤치마크 바이어스를 전면 제거하지 않고 `demoMode` 플래그로 분리하여 데모 시연 안정성 확보.

### 의사결정 드라이버 (Decision Drivers)

1. **타입 안전성**: `Record<string, number>`로의 완전 교체는 컴파일 타임 타입 검증을 잃는다. Additive 접근이 안전.
2. **Ripple Effect 최소화**: `ScoredCandidate` 구조 변경시 `CandidateCard`, `EvolutionEvent`, orchestrator 매핑이 동시에 깨진다. Phase 1에서 일괄 처리 필수.
3. **LLM 비용/예측가능성**: 진화 알고리즘 파라미터까지 LLM에 위임하면 비결정적 동작이 과도해진다. 차원+가중치+프롬프트만 위임.

### 실행 가능 옵션 (Viable Options)

#### Option A: Additive-Only + demoMode 분리 (채택)
- 기존 3개 명시적 필드 유지 + `scores?: Record<string, number>` 추가
- 벤치마크 바이어스를 `demoMode` 플래그로 분리
- LLM 위임 범위를 차원/가중치/프롬프트로 제한
- **장점**: 타입 안전성 보존, 하위 호환 100%, 데모 안정성, ripple effect 최소
- **단점**: 이중 구조(명시적 필드 + scores)로 인한 약간의 코드 중복

#### Option B: Record<string, number> 완전 교체 (기각)
- v1 원안대로 `Record<string, number>`로 완전 교체
- **기각 사유**: 컴파일 타임 타입 체크 상실, downstream 13곳 이상 동시 변경 필요, 기존 DB 데이터와의 호환성 복잡도 증가

---

## Architect 제안 채택/기각 결정

### A-1. Phase 1 additive-only 전략 -- **채택**

> 제안: `Record<string, number>`로 완전 교체 대신, 기존 명시적 필드 유지 + `scores?: Record<string, number>` 추가

**결정: 채택.** 근거:
- `logicalConsistency`, `evidenceGrounding`, `solutionUsefulness`를 삭제하면 `ScoredCandidate`, `EvolutionEvent`, `CandidateCard`, `CandidateJudgeResult` 등 모든 downstream 타입이 동시에 깨진다.
- Additive 접근으로 기존 3개 필드를 유지하면서 `scores?: Record<string, number>`를 추가하면, 기존 코드는 변경 없이 동작하고, 새 코드는 `scores`를 사용할 수 있다.
- `calculateFitness`는 `scores` 필드가 있을 때 동적 계산, 없을 때 기존 3개 필드로 계산하는 이중 경로 제공.

**구현 영향:** Phase 1의 범위가 크게 줄어든다. 기존 코드 수정 최소화.

### A-2. Phase 4 LLM 위임 범위 축소 -- **채택**

> 제안: `planEvolutionStrategy`에서 차원 설계 + 가중치 + 프롬프트만 LLM 위임. survivorCount, threshold 등 수치 알고리즘 파라미터는 기본값 유지.

**결정: 채택.** 근거:
- survivorCount, threshold, generationLimit 등을 LLM이 결정하면 비결정적 동작이 과도해진다.
- 이 파라미터들은 알고리즘적 튜닝 영역이므로 기본값이 합리적이다.
- LLM은 "무엇을 평가할지"(차원명, 가중치)와 "어떤 관점으로 평가할지"(프롬프트)만 결정.

**구현 영향:** `planEvolutionStrategy` 반환 타입이 축소된다. `populationLimit`, `generationLimit`, `threshold`는 기존 하드코딩 값 유지.

### A-3. 벤치마크 바이어스 demoMode 분리 -- **채택**

> 제안: `demoMode?: boolean` 플래그로 분리 (전면 제거 대신). 데모 경험 보존.

**결정: 채택.** 근거:
- 바이어스를 전면 제거하면 car-wash 데모가 LLM 품질에 100% 의존하게 되어 시연 불안정.
- `demoMode: true`일 때만 기존 바이어스 로직 활성화, `false`(기본값)일 때는 순수 LLM 평가.
- `isSeededBenchmark()` 하드코딩 판별 대신, 명시적 플래그로 전환하면 코드 의도가 명확해진다.

**구현 영향:** `isSeededBenchmark()` 함수와 `applyBenchmarkBias()` 함수는 `demoMode` 조건 분기로 리팩터링.

### A-4. Phase 0 추가 (두 번째 벤치마크) -- **채택 (변형)**

> 제안: 두 번째 벤치마크 추가로 현재 엔진의 한계를 실증.

**결정: 채택하되, 독립 Phase가 아닌 Phase 5 통합 검증에 포함.** 근거:
- 별도 Phase 0으로 분리하면 실제 코드 변경 없이 벤치마크만 추가하는 것이므로 Phase로서의 의미가 약하다.
- Phase 5의 통합 검증에서 car-wash 외 추가 벤치마크(예: 수학 추론, 다단계 논리)로 엔진 한계를 실증하는 것이 자연스럽다.
- 실증 결과를 문서화하여 향후 개선 방향의 근거로 남긴다.

---

## Critic 개선 사항 반영

### C-1. [Critical] Phase 1-4 간 CandidateCard 의존성 충돌 -- **반영 완료**

> 문제: Phase 1에서 `EvolutionEvent.candidate.scored`를 변경하면 orchestrator.ts L511-527의 `CandidateCard` 매핑이 즉시 깨짐.

**해결:** Additive-only 전략 채택(A-1)으로 이 문제가 대폭 완화된다. 기존 3개 명시적 필드가 유지되므로 기존 `CandidateCard` 매핑은 깨지지 않는다. 단, Phase 1에서 `scores` 필드 추가시 `CandidateCard`와 `EvolutionEvent`에도 `scores?` optional 필드를 **동시에** 추가하여 일관성을 유지한다. orchestrator.ts의 매핑 코드도 Phase 1에서 `scores` 전달을 추가한다.

### C-2. [Critical] judgeResponseSchema (Zod) 동적화 미명시 -- **반영 완료**

> 문제: orchestrator.ts L103-107의 `judgeResponseSchema` (Zod 스키마)도 동적으로 생성되어야 함.

**해결:** Phase 4에 명시적 TODO 추가. `judgeResponseSchema`(Zod)와 `judgeSchema`(JSON Schema) 양쪽 모두 동적 생성 함수로 교체.
- `buildJudgeSchema(dimensions)` -> JSON Schema (LLM structured output용)
- `buildJudgeResponseSchema(dimensions)` -> Zod schema (응답 파싱/검증용)

### C-3. [Critical] Architect 4가지 제안에 대한 명시적 결정 -- **반영 완료**

위의 "Architect 제안 채택/기각 결정" 섹션에서 각각 채택/기각/변형 결정과 근거를 명시.

### C-4. [Medium] candidateListSchema의 minItems: 3 동적화 -- **반영 완료**

> 문제: `planEvolutionStrategy`가 `candidateCount`를 반환하면 `candidateListSchema`와 `candidateListResponseSchema`(Zod)도 동적으로 바뀌어야 함.

**해결:** Phase 4에 명시적 TODO 추가.
- `buildCandidateListSchema(candidateCount)` -> JSON Schema 동적 생성
- `buildCandidateListResponseSchema(candidateCount)` -> Zod `.min(candidateCount)` 동적 생성

### C-5. [Minor] 테스트 수 정정 + open-questions 해결 시점 매핑 -- **반영 완료**

> 문제: v1에서 "기존 22개 테스트"라고 명시했으나 실제와 다름.

**정정:** 실제 테스트 수는 **11개** (core: 5개, web/dashboard-presenters: 6개). 계획 전체에서 정확한 수치로 수정. open-questions의 해결 시점을 각 Phase에 매핑.

---

## Phase 의존관계 다이어그램

```
Phase 1 (타입 additive 확장)
    |
    v
Phase 2 (엔진 파라미터 유연화) -----> Phase 3 (평가 체계 동적화)
    |                                      |
    v                                      v
Phase 4 (오케스트레이터 LLM 위임 + demoMode 분리)
    |
    v
Phase 5 (UI 동적 렌더링 + 통합 검증 + 추가 벤치마크 실증)
```

**권장 시작 순서: Phase 1 -> 2 -> 3 -> 4 -> 5**

Phase 1은 나머지 모든 Phase의 기반이므로 반드시 먼저 완료해야 한다. Phase 2와 3은 서로 독립적이나, Phase 4가 둘 다 의존하므로 순차 진행을 권장한다.

---

## Phase 1: 타입 시스템 Additive 확장 (기반 작업)

### 목적
기존 3차원 명시적 필드를 **유지**하면서, 동적 차원을 지원하는 `scores` 필드를 **추가**한다. 하위 호환성 100% 보존. 동시에 `CandidateCard`, `EvolutionEvent`에도 동일한 additive 확장을 적용하여 Phase 4에서의 의존성 충돌을 사전 방지한다.

### 변경 파일 및 내용

#### 1-1. `packages/core/src/types.ts` - 타입 Additive 확장

**현재:**
```typescript
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
```

**변경 후 (기존 필드 유지 + 신규 필드 추가):**
```typescript
// 기존 3개 필드 유지 (타입 안전성 보존)
export type JudgeWeights = {
  logicalConsistency: number;
  evidenceGrounding: number;
  solutionUsefulness: number;
  // 동적 차원 지원: 기존 3개 외 추가 차원의 가중치
  [dimension: string]: number;
};

export type CandidateJudgeResult = {
  logicalConsistency: number;
  evidenceGrounding: number;
  solutionUsefulness: number;
  // 동적 차원 지원: 기존 3개 외 추가 차원의 점수
  [dimension: string]: number;
};

// 기본 차원 상수 (삭제하지 않음)
export const DEFAULT_JUDGE_DIMENSIONS = [
  "logicalConsistency",
  "evidenceGrounding",
  "solutionUsefulness"
] as const;
export type DefaultJudgeDimension = typeof DEFAULT_JUDGE_DIMENSIONS[number];
```

**`ScoredCandidate` - additive 확장:**
```typescript
// 기존: Candidate & CandidateJudgeResult & { fitness, critique, benchmarkVerdict }
// 변경: 기존 구조 유지 + scores 필드 추가
export type ScoredCandidate = Candidate &
  CandidateJudgeResult & {
    fitness: number;
    critique: string[];
    benchmarkVerdict: BenchmarkVerdict;
    // 동적 차원 전체 점수 (기존 3개 포함). Phase 4에서 활용.
    scores?: Record<string, number>;
  };
```

**`EvolutionEvent`의 `candidate.scored` - additive 확장:**
```typescript
| {
    type: "candidate.scored";
    generation: number;
    candidateId: string;
    answer: string;
    fitness: number;
    // 기존 3개 필드 유지
    logicalConsistency: number;
    evidenceGrounding: number;
    solutionUsefulness: number;
    // 동적 차원 전체 점수 추가 (optional, Phase 4에서 채워짐)
    scores?: Record<string, number>;
    critique: string[];
    benchmarkPassed: boolean;
  }
```

#### 1-2. `packages/core/src/scoring.ts` - 동적 가중합 계산 지원

**현재:** 3개 필드를 직접 곱하여 합산
**변경:** `scores` 필드가 있으면 동적 계산, 없으면 기존 3개 필드 계산

```typescript
export const DEFAULT_JUDGE_WEIGHTS: JudgeWeights = {
  logicalConsistency: 0.5,
  evidenceGrounding: 0.2,
  solutionUsefulness: 0.3
};

export function calculateFitness(
  result: CandidateJudgeResult,
  weights: JudgeWeights = DEFAULT_JUDGE_WEIGHTS,
  scores?: Record<string, number>
): number {
  // 동적 차원이 제공된 경우: scores 키를 순회하며 가중합
  if (scores && Object.keys(scores).length > 0) {
    let total = 0;
    for (const key of Object.keys(weights)) {
      total += (scores[key] ?? 0) * weights[key];
    }
    return total;
  }
  // 기존 경로: 명시적 3개 필드로 계산 (하위 호환)
  return (
    result.logicalConsistency * weights.logicalConsistency +
    result.evidenceGrounding * weights.evidenceGrounding +
    result.solutionUsefulness * weights.solutionUsefulness
  );
}
```

#### 1-3. `packages/core/src/engine.ts` - scores 필드 채우기

- `scoreCandidate` 함수에서 `ScoredCandidate` 생성시 `scores` 필드를 기존 3개 값으로 채움
- `candidate.scored` 이벤트 발행시 `scores` 필드 추가
- 나머지 엔진 로직(sortByFitness, pickBest 등)은 `fitness` 필드를 사용하므로 변경 없음

```typescript
// scoreCandidate 반환부:
return {
  ...candidate,
  ...judgeResult,
  critique,
  fitness,
  benchmarkVerdict,
  scores: { ...judgeResult }  // 기존 3개 필드를 scores에도 복사
} satisfies ScoredCandidate;
```

#### 1-4. `apps/web/src/lib/types.ts` - CandidateCard additive 확장

**기존 필드 유지 + scores 추가:**
```typescript
export type CandidateCard = {
  id: string;
  answer: string;
  generation: number;
  fitness: number;
  // 기존 3개 필드 유지 (하위 호환)
  logicalConsistency: number;
  evidenceGrounding: number;
  solutionUsefulness: number;
  // 동적 차원 전체 점수 (optional, Phase 4에서 활용)
  scores?: Record<string, number>;
  critique: string[];
  benchmarkPassed: boolean;
  parents: string[];
  source: "seed" | "mutation" | "crossover";
  selected: boolean;
};
```

#### 1-5. `apps/web/src/lib/orchestrator.ts` - CandidateCard 매핑에 scores 추가

orchestrator.ts L510-527의 `updateRun` 콜백에서 `scores` 필드도 전달:
```typescript
// 기존 매핑 유지 + scores 추가
{
  id: event.candidateId,
  answer: event.answer,
  generation: origin.generation,
  fitness: event.fitness,
  logicalConsistency: event.logicalConsistency,
  evidenceGrounding: event.evidenceGrounding,
  solutionUsefulness: event.solutionUsefulness,
  scores: event.scores,  // 추가
  critique: event.critique,
  benchmarkPassed: event.benchmarkPassed,
  parents: origin.parents,
  source: origin.source,
  selected: false
}
```

#### 1-6. 테스트 업데이트

- `packages/core/tests/scoring.test.ts`: 기존 테스트 통과 확인 + 동적 차원 `scores` 경로 테스트 1개 추가 (4차원 가중합)
- `packages/core/tests/engine.test.ts`: 기존 테스트 통과 확인 + `scores` 필드 존재 검증 assertion 추가
- `apps/web/src/lib/dashboard-presenters.test.ts`: `CandidateCard` 테스트 데이터에 `scores?` 필드 추가 (optional이므로 기존 테스트는 그대로 통과)

### 수락 기준
- [ ] `JudgeWeights`와 `CandidateJudgeResult`가 기존 3개 명시적 필드를 유지하면서 index signature로 추가 차원을 허용한다
- [ ] `ScoredCandidate`에 `scores?: Record<string, number>` 필드가 추가된다
- [ ] `EvolutionEvent.candidate.scored`에 `scores?: Record<string, number>` 필드가 추가된다
- [ ] `CandidateCard`에 `scores?: Record<string, number>` 필드가 추가된다
- [ ] orchestrator.ts의 CandidateCard 매핑이 `scores`를 전달한다
- [ ] 기존 11개 테스트가 변경 없이 모두 통과한다
- [ ] 4차원 커스텀 가중치로 `calculateFitness`의 `scores` 경로가 올바르게 계산된다
- [ ] `pnpm typecheck` 통과

### 위험성: **낮음** (v1 대비 하향)
- Additive-only이므로 기존 코드에 대한 breaking change 없음
- index signature 추가로 인한 타입 호환성은 TypeScript에서 자연스럽게 처리됨

---

## Phase 2: 진화 엔진 파라미터 유연화

### 목적
하드코딩된 진화 파라미터(생존자 수, 변이 대상/수, 교차 조건 등)를 `RunReasonForgeCycleInput`의 선택적 설정으로 추출한다. 기본값은 현재 동작을 그대로 유지한다.

**참고:** Architect A-2 결정에 따라 이 파라미터들은 LLM이 결정하지 않는다. 코드에서 명시적으로 설정하거나 기본값을 사용한다.

### 변경 파일 및 내용

#### 2-1. `packages/core/src/types.ts` - 진화 전략 설정 타입 추가

```typescript
export type EvolutionStrategy = {
  /** 각 세대에서 선택할 생존자 수 (기본값: 2) */
  survivorCount?: number;
  /** 변이 대상 선택 방식 (기본값: "best") */
  mutationTarget?: "best" | "random" | "all-survivors";
  /** 변이당 생성할 후보 수 (기본값: 1) */
  mutationsPerTarget?: number;
  /** 교차 실행 조건 (기본값: 기존 로직 - threshold 미달시) */
  crossoverPolicy?: "always" | "when-below-threshold" | "never";
  /** 피트니스 가중치 (기본값: DEFAULT_JUDGE_WEIGHTS) */
  weights?: JudgeWeights;
};

// RunReasonForgeCycleInput에 추가:
export type RunReasonForgeCycleInput = {
  // ... 기존 필드 ...
  strategy?: EvolutionStrategy;
};
```

#### 2-2. `packages/core/src/engine.ts` - 전략 적용

- 생존자 선택: `Math.min(2, population.length)` -> `Math.min(strategy.survivorCount ?? 2, population.length)`
- 변이 대상: `best` 1개만 -> `mutationTarget` 설정에 따라 대상 선택
- 변이 수: 1개 -> `mutationsPerTarget`만큼 반복
- 교차 조건: 하드코딩된 조건 -> `crossoverPolicy`에 따라 결정
- `calculateFitness` 호출시 `strategy.weights` 전달

#### 2-3. 테스트

- 기존 테스트: `strategy` 미지정시 현재와 동일하게 동작 확인
- 새 테스트: `survivorCount: 3`, `mutationsPerTarget: 2` 등 커스텀 전략으로 세대 진행 검증

### 수락 기준
- [ ] `EvolutionStrategy` 타입이 정의되고 `RunReasonForgeCycleInput`에 포함된다
- [ ] `strategy` 미지정시 현재와 100% 동일한 동작을 한다
- [ ] `survivorCount`, `mutationsPerTarget`, `crossoverPolicy` 각각이 독립적으로 동작한다
- [ ] 기존 테스트 통과 + 새 전략 테스트 최소 3개 추가

### 위험성: **낮음**
- 모든 신규 필드가 optional이며, 기본값이 현재 동작과 동일
- core 내부 변경이므로 외부 인터페이스 영향 없음

---

## Phase 3: 평가 체계 동적화

### 목적
고정된 종료 조건(fitness + benchmark)과 정렬 전략(fitness 내림차순)을 설정 가능하게 만들고, 벤치마크 정답 매칭을 유연화한다.

### 변경 파일 및 내용

#### 3-1. `packages/core/src/types.ts` - 종료/선택 전략 타입

```typescript
export type TerminationCondition = {
  /** 피트니스 종료 조건 사용 여부 (기본값: true) */
  useFitnessThreshold?: boolean;
  /** 벤치마크 통과 필수 여부 (기본값: true) */
  requireBenchmarkPass?: boolean;
  /** 커스텀 종료 판단 함수 (제공시 기본 조건 대신 사용) */
  custom?: (candidate: ScoredCandidate) => boolean;
};

export type SelectionStrategy = {
  /** 정렬 기준 (기본값: "fitness-desc") */
  sortBy?: "fitness-desc" | "fitness-asc" | ((a: ScoredCandidate, b: ScoredCandidate) => number);
};
```

**`EvolutionStrategy`에 통합:**
```typescript
export type EvolutionStrategy = {
  // ... Phase 2 필드 ...
  termination?: TerminationCondition;
  selection?: SelectionStrategy;
};
```

#### 3-2. `packages/core/src/engine.ts` - 조건부 종료 및 정렬

- `sortByFitness`를 `sortPopulation(population, strategy)`로 일반화
- 종료 조건 체크를 `shouldTerminate(best, input)` 함수로 추출
- 현재의 `best.fitness >= input.threshold && best.benchmarkVerdict.passed` 로직을 기본값으로 유지

#### 3-3. `packages/core/src/benchmark.ts` - 매칭 전략 유연화

```typescript
export type BenchmarkMatcher = (expected: string, answer: string) => boolean;

// 기본 매처: 현재의 .includes() 로직
export const defaultBenchmarkMatcher: BenchmarkMatcher = (expected, answer) =>
  normalizeAnswer(answer).includes(expected.toLowerCase());

// BenchmarkCase에 matcher 필드 추가 (optional)
export type BenchmarkCase = {
  id: string;
  label: string;
  prompt: string;
  expectedAnswer: string;
  matcher?: BenchmarkMatcher;
};
```

#### 3-4. 테스트

- 기존 벤치마크 테스트가 기본 매처로 통과
- 커스텀 매처 테스트 (예: 정규식 매칭, 정확 일치)
- 커스텀 종료 조건 테스트 (예: fitness만으로 종료, 벤치마크 무시)

### 수락 기준
- [ ] `TerminationCondition`, `SelectionStrategy` 타입이 정의된다
- [ ] 기본 설정시 현재와 동일하게 동작한다
- [ ] 커스텀 종료 조건으로 벤치마크 없이 fitness만으로 종료 가능하다
- [ ] 커스텀 정렬 함수로 다른 기준 정렬이 가능하다
- [ ] `BenchmarkCase`에 커스텀 매처를 지정할 수 있다

### 위험성: **낮음**
- Phase 2와 동일하게 모든 신규 필드가 optional
- `BenchmarkCase` 타입 변경이 유일한 외부 영향이나, 기존 필드는 그대로이므로 호환

---

## Phase 4: 오케스트레이터 LLM 위임 + demoMode 분리

### 목적
오케스트레이터에서 평가 차원/가중치/프롬프트를 LLM 판단으로 대체하고, `isSeededBenchmark` 바이어스를 `demoMode` 플래그로 분리하며, 스키마(JSON Schema + Zod)를 동적으로 생성한다.

### 변경 파일 및 내용

#### 4-1. `apps/web/src/lib/orchestrator.ts` - LLM 기반 차원/가중치 결정

**새 함수: `planEvolutionStrategy`**
```typescript
// LLM에게 질문의 특성을 분석하게 하여 평가 차원, 가중치, 프롬프트를 반환
async function planEvolutionStrategy(
  prompt: string,
  model: string
): Promise<{
  // LLM이 결정하는 항목:
  dimensions: string[];       // 평가 차원 (예: ["logicalConsistency", "creativity", "practicalFeasibility"])
  dimensionWeights: JudgeWeights;  // 각 차원의 가중치
  candidateCount: number;     // 초기 후보 수 (3-7)
  evaluationPrompt: string;   // 차원별 평가 지시 프롬프트
}> {
  // LLM에게 질문 분석 + 차원 설계를 요청하는 structured prompt
  // 범위 제한: candidateCount 3-7, dimensions 3-7개
  // fallback: 현재 하드코딩 값과 동일한 기본값
}
```

**참고 (Architect A-2 반영):** `populationLimit`, `generationLimit`, `threshold`, `survivorCount` 등 수치 알고리즘 파라미터는 LLM에 위임하지 않고 기존 기본값을 유지한다.

#### 4-2. `apps/web/src/lib/orchestrator.ts` - 스키마 동적 생성 (Critic C-2, C-4 반영)

**JSON Schema 동적 생성 (LLM structured output용):**
```typescript
function buildJudgeSchema(dimensions: string[]) {
  return {
    type: "object",
    additionalProperties: false,
    required: dimensions,
    properties: Object.fromEntries(
      dimensions.map(dim => [dim, { type: "number" }])
    )
  };
}

function buildCandidateListSchema(candidateCount: number) {
  return {
    type: "object",
    additionalProperties: false,
    required: ["candidates"],
    properties: {
      candidates: {
        type: "array",
        minItems: candidateCount,
        items: {
          type: "object",
          additionalProperties: false,
          required: ["answer", "steps"],
          properties: {
            answer: { type: "string" },
            steps: { type: "array", items: { type: "string" }, minItems: 2 }
          }
        }
      }
    }
  };
}
```

**Zod 스키마 동적 생성 (응답 파싱/검증용):**
```typescript
function buildJudgeResponseSchema(dimensions: string[]) {
  const shape: Record<string, z.ZodNumber> = {};
  for (const dim of dimensions) {
    shape[dim] = z.number();
  }
  return z.object(shape);
}

function buildCandidateListResponseSchema(candidateCount: number) {
  return z.object({
    candidates: z
      .array(
        z.object({
          answer: z.string(),
          steps: z.array(z.string()).min(2)
        })
      )
      .min(candidateCount)
  });
}
```

**기존 정적 스키마 변수 (`judgeSchema`, `judgeResponseSchema`, `candidateListSchema`, `candidateListResponseSchema`)는 기본값으로 유지하되, `runReasonForge` 함수 내에서 동적 스키마로 오버라이드된다.**

#### 4-3. `apps/web/src/lib/orchestrator.ts` - demoMode 분리 (Architect A-3 반영)

**`isSeededBenchmark()` -> `demoMode` 플래그 전환:**

```typescript
// 기존 함수를 유지하되 demoMode 헬퍼로 리팩터링
function isDemoMode(prompt: string, demoMode?: boolean): boolean {
  if (demoMode !== undefined) return demoMode;
  // 레거시 호환: 기존 seeded benchmark 감지 (향후 제거 예정)
  return prompt.trim() === getDefaultBenchmarkCase().prompt.trim();
}
```

**6곳의 `isSeededBenchmark` 호출을 `isDemoMode` 호출로 교체:**
1. `generatePopulation`: `isDemoMode(prompt, demoMode)` 분기
2. `critiqueCandidate`: `isDemoMode(prompt, demoMode)` 분기
3. `mutateCandidate`: `isDemoMode(prompt, demoMode)` 분기
4. `judgeCandidate`: `isDemoMode(prompt, demoMode)` 분기 (정답 힌트)
5. `applyBenchmarkBias`: `isDemoMode` 조건 하에서만 적용
6. `runReasonForge`의 benchmark 할당: `isDemoMode` 조건 하에서만 기본 벤치마크 사용

**`orchestrate` 함수에 `demoMode?: boolean` 파라미터 추가. UI에서 토글 가능.**

#### 4-4. `apps/web/src/lib/orchestrator.ts` - 프롬프트 동적화

- 현재: 모든 문제에 동일한 프롬프트 ("Generate 3 diverse candidate reasoning chains...")
- 변경: `planEvolutionStrategy`에서 결정된 `evaluationPrompt`와 `candidateCount`를 사용
- 프롬프트에 동적 차원명과 평가 기준이 포함됨

#### 4-5. `apps/web/src/lib/orchestrator.ts` - `runReasonForge` 통합

`runReasonForge` 함수에서:
- `planEvolutionStrategy`를 호출하여 LLM으로부터 차원/가중치/프롬프트를 받음
- 받은 차원으로 동적 스키마(JSON Schema + Zod) 생성
- `judgeCandidate`가 동적 차원 스키마를 사용
- `generatePopulation`이 LLM이 정한 `candidateCount`를 사용
- 결과의 `scores` 필드에 동적 차원 점수가 채워짐

#### 4-6. 테스트 업데이트

- `apps/web/src/lib/dashboard-presenters.test.ts`: `CandidateCard` 테스트 데이터에 `scores` 필드 추가 (기존 테스트는 scores가 optional이므로 통과)
- 새 테스트: `buildJudgeSchema`, `buildJudgeResponseSchema`, `buildCandidateListSchema`, `buildCandidateListResponseSchema` 각각의 동적 생성 검증
- 새 테스트: `isDemoMode` 함수의 3가지 경로 (true/false/auto-detect) 검증

### 수락 기준
- [ ] `planEvolutionStrategy`가 LLM 호출로 차원/가중치/프롬프트를 반환한다
- [ ] `judgeSchema`와 `judgeResponseSchema`가 동적 차원 기반으로 생성된다 (Critic C-2)
- [ ] `candidateListSchema`와 `candidateListResponseSchema`가 동적 `candidateCount` 기반으로 생성된다 (Critic C-4)
- [ ] `isSeededBenchmark` 호출이 `isDemoMode` 호출로 교체된다
- [ ] `demoMode: true`일 때 기존 바이어스 로직이 동작한다
- [ ] `demoMode: false`(기본)일 때 모든 바이어스가 비활성화된다
- [ ] 프롬프트가 문제 유형에 따라 다르게 생성된다
- [ ] `planEvolutionStrategy` 실패시 기존 3차원 기본값으로 fallback한다
- [ ] 기존 11개 테스트 통과 + 스키마 빌더 테스트 4개 + isDemoMode 테스트 3개 추가

### 위험성: **높음**
- LLM 호출 추가로 latency 증가
- 동적 스키마 생성의 런타임 오류 가능성
- **완화 전략:**
  - `planEvolutionStrategy`에 합리적 기본값 fallback 제공
  - LLM 전략 플래닝 호출에 timeout 설정
  - demoMode로 데모 안정성 확보
  - 스키마 빌더에 대한 단위 테스트로 런타임 오류 사전 방지

---

## Phase 5: UI 동적 렌더링 + 통합 검증 + 추가 벤치마크 실증

### 목적
대시보드 UI가 동적 차원을 렌더링하도록 업데이트하고, 전체 파이프라인의 end-to-end 동작을 검증한다. 추가 벤치마크로 엔진 한계를 실증한다 (Architect A-4 반영).

### 변경 파일 및 내용

#### 5-1. `apps/web/src/components/dashboard-app.tsx` - 동적 차원 렌더링

**현재 `candidate-card`에서:**
- fitness만 표시하고 개별 차원은 `CandidateCard` 타입에만 존재
- `applyEvent`의 `reasonforge.candidateScored`에서 `CandidateCard`로 캐스팅

**변경:**
- `applyEvent`에서 `scores` 객체가 있으면 동적 차원 렌더링
- candidate card에 `scores`가 있을 때 `Object.entries(candidate.scores)`로 순회하여 표시
- `scores`가 없을 때(레거시 데이터) 기존 3개 필드로 fallback 표시
- 차원명을 사람이 읽기 좋게 변환하는 유틸리티 함수 사용

#### 5-2. `apps/web/src/lib/dashboard-presenters.ts` - 차원 표시 유틸리티

```typescript
export function formatDimensionName(key: string): string {
  // camelCase를 "Logical Consistency" 형태로 변환
  return key
    .replace(/([A-Z])/g, " $1")
    .replace(/^./, (char) => char.toUpperCase())
    .trim();
}
```

#### 5-3. 통합 검증 + 추가 벤치마크 실증 (Architect A-4)

- **기존 벤치마크 검증:** car-wash 벤치마크를 `demoMode: true`와 `demoMode: false` 양쪽으로 실행
- **추가 벤치마크 실증:** 새로운 질문(예: 수학 추론, 다단계 논리)으로 실행하여:
  - LLM이 적절한 차원과 가중치를 선택하는지 확인
  - 기존 3차원 고정 평가 대비 동적 차원 평가의 차이 문서화
  - 현재 엔진의 한계(예: 특정 유형에서 수렴 실패)를 실증 데이터로 기록
- **UI 검증:** 동적 차원이 올바르게 렌더링되는지 확인

### 수락 기준
- [ ] UI가 `scores` 객체의 모든 키를 동적으로 렌더링한다
- [ ] `scores`가 없는 레거시 데이터도 기존 3개 필드로 정상 표시된다
- [ ] 3차원, 4차원, 5차원 등 다양한 차원 수에서 UI가 깨지지 않는다
- [ ] `demoMode: true`로 car-wash 벤치마크가 안정적으로 동작한다
- [ ] `demoMode: false`로 새 질문에 대해 LLM이 동적 차원을 생성한다
- [ ] 추가 벤치마크 실증 결과가 문서화된다
- [ ] 전체 테스트 스위트가 통과한다

### 위험성: **낮음**
- UI 변경만이므로 core/engine에 영향 없음
- 동적 렌더링은 `Object.entries` 순회이므로 단순

---

## Phase 간 호환성 유지 전략

### 하위 호환성 레이어

| Phase | 호환 전략 |
|-------|-----------|
| 1 | Additive-only: 기존 3개 명시적 필드 유지 + `scores?` optional 추가. 모든 기존 코드가 변경 없이 동작 |
| 2 | `EvolutionStrategy`의 모든 필드가 optional. 미지정시 현재 하드코딩 값과 동일 |
| 3 | `TerminationCondition`, `SelectionStrategy`도 모두 optional. `BenchmarkCase.matcher`도 optional |
| 4 | `planEvolutionStrategy` 실패시 하드코딩된 기본값으로 fallback. `demoMode` 미지정시 레거시 auto-detect |
| 5 | UI는 `scores` 객체 유무를 체크하여 레거시 데이터도 표시 가능하게 처리 |

### DB 호환성
- DB는 `data_json` TEXT 컬럼에 JSON blob으로 저장하므로 스키마 변경 불필요
- 기존 저장된 RunRecord에 `scores` 필드가 없을 수 있으므로, 읽기시 마이그레이션 유틸리티 제공:
  ```typescript
  function migrateCandidateCard(card: any): CandidateCard {
    if (card.scores) return card;
    return {
      ...card,
      scores: {
        logicalConsistency: card.logicalConsistency ?? 0,
        evidenceGrounding: card.evidenceGrounding ?? 0,
        solutionUsefulness: card.solutionUsefulness ?? 0
      }
    };
  }
  ```

---

## 파일별 변경 요약

| 파일 | Phase | 변경 유형 |
|------|-------|-----------|
| `packages/core/src/types.ts` | 1, 2, 3 | Additive 타입 확장 (index signature, scores?, EvolutionStrategy, TerminationCondition, SelectionStrategy) |
| `packages/core/src/scoring.ts` | 1 | 이중 경로 fitness 계산 (scores 경로 + 기존 경로) |
| `packages/core/src/engine.ts` | 1, 2, 3 | scores 필드 채우기, 전략 파라미터 적용, 종료/선택 유연화 |
| `packages/core/src/benchmark.ts` | 3 | 커스텀 매처 지원 |
| `packages/core/src/index.ts` | 1 | export 추가 (DEFAULT_JUDGE_DIMENSIONS 등) |
| `packages/core/tests/scoring.test.ts` | 1 | 동적 차원 scores 경로 테스트 추가 |
| `packages/core/tests/engine.test.ts` | 1, 2 | scores 필드 검증 + 전략 테스트 |
| `packages/core/tests/benchmark.test.ts` | 3 | 커스텀 매처 테스트 |
| `apps/web/src/lib/types.ts` | 1 | CandidateCard에 scores? 추가 |
| `apps/web/src/lib/orchestrator.ts` | 1, 4 | Phase 1: scores 매핑 추가. Phase 4: LLM 위임, demoMode 분리, 동적 스키마 |
| `apps/web/src/lib/dashboard-presenters.ts` | 5 | 차원명 포맷 유틸리티 |
| `apps/web/src/lib/dashboard-presenters.test.ts` | 1, 5 | scores 필드 추가, 포맷 유틸리티 테스트 |
| `apps/web/src/components/dashboard-app.tsx` | 5 | 동적 차원 렌더링 |

---

## 각 Phase 검증 방법

| Phase | 검증 방법 |
|-------|-----------|
| 1 | `pnpm test` (기존 11개 테스트 전체 통과) + `pnpm typecheck` + 신규 scores 경로 테스트 통과 |
| 2 | `pnpm test` + 새 전략 파라미터 테스트 통과 |
| 3 | `pnpm test` + 커스텀 종료조건/매처 테스트 통과 |
| 4 | `pnpm test` + `pnpm typecheck` + 스키마 빌더/isDemoMode 테스트 통과 + 수동으로 demoMode=true/false 실행 |
| 5 | `pnpm test` + `pnpm dev`로 UI 확인 + 추가 벤치마크 실증 + 레거시 데이터 호환성 확인 |

---

## 위험성 요약 및 완화 전략

| 위험 | 등급 | 완화 |
|------|------|------|
| Phase 1 타입 변경의 ripple effect | **낮음** (v1 중간에서 하향) | Additive-only로 breaking change 없음. index signature는 기존 객체와 호환 |
| CandidateCard 의존성 충돌 (Critic C-1) | **해소됨** | Phase 1에서 CandidateCard, EvolutionEvent 동시 additive 확장. 기존 매핑 코드 불변 |
| Zod/JSON Schema 동적화 런타임 오류 (Critic C-2, C-4) | 중간 | 스키마 빌더 단위 테스트 4개로 사전 검증. fallback으로 기존 정적 스키마 유지 |
| 벤치마크 바이어스 제거로 인한 데모 불안정 | **해소됨** | demoMode 플래그로 분리. 데모시 demoMode=true로 안정성 확보 |
| LLM 전략 플래닝의 latency 추가 | 중간 | timeout + fallback 기본값. 전략 플래닝은 1회만 호출 |
| 기존 DB 데이터와의 호환성 | 낮음 | scores가 optional이므로 레거시 데이터 그대로 동작. migrateCandidateCard로 런타임 변환 |
| UI에서 동적 차원의 레이아웃 깨짐 | 낮음 | CSS grid/flex로 동적 대응. 차원 수 제한(최대 7개) 방어 코드 |

---

## Open Questions 해결 시점 매핑

| Open Question | 해결 Phase | 결정 |
|--------------|-----------|------|
| LLM 호출 비용/latency 예산 | Phase 4 | 경량 모델(haiku급)로 전략 플래닝, timeout 5초, fallback 기본값 |
| seeded car-wash 벤치마크를 데모로 유지할지 | Phase 4 | **demoMode 플래그로 해결** - 데모시 유지, 실제 사용시 비활성화 |
| dimensions 최대 개수 제한 | Phase 4 | 최대 7개로 제한 (UI 레이아웃 + 피트니스 정밀도 고려) |
| 프롬프트 동적화 범위 | Phase 4 | LLM이 evaluationPrompt를 자유 생성 (반자율이 아닌 자율, 단 범위 제한 내) |
| MCP 전환시 EvolutionStrategy 노출 | Phase 2-3 설계시 고려 | 타입을 JSON-serializable하게 설계 (함수 타입은 string enum으로 대체 가능하게) |
| 기존 DB 마이그레이션 방식 | Phase 5 | 런타임 lazy 마이그레이션 (migrateCandidateCard) |

---

## ADR: 아키텍처 결정 기록

### Decision
ReasonForge 진화 엔진을 Additive-Only 전략으로 유연화한다. 기존 타입의 명시적 필드를 유지하면서 동적 차원을 지원하는 `scores` 필드를 추가하고, 벤치마크 바이어스를 `demoMode` 플래그로 분리하며, LLM 위임 범위를 차원/가중치/프롬프트로 제한한다.

### Drivers
1. 하위 호환성 100% 보존 (기존 11개 테스트, DB 데이터, UI 모두 무변경 동작)
2. 타입 안전성 유지 (컴파일 타임 검증 보존)
3. 데모 경험 안정성 (demoMode로 분리)

### Alternatives Considered
- **Option B (Record 완전 교체)**: 타입 안전성 상실, 13곳 이상 동시 변경으로 인한 높은 ripple effect. 기각.
- **Option C (벤치마크 바이어스 전면 제거)**: 데모 시연 불안정. demoMode 분리로 대체.
- **Option D (LLM에 알고리즘 파라미터까지 위임)**: 비결정적 동작 과도. 차원/가중치/프롬프트만 위임.

### Why Chosen
Additive-Only가 가장 낮은 위험으로 동적 차원 지원을 달성한다. 기존 코드의 breaking change가 제로이므로 각 Phase를 안전하게 독립 배포할 수 있다.

### Consequences
- 이중 구조(명시적 필드 + scores)로 인한 약간의 코드 중복
- Phase 4에서 orchestrator가 `scores` 필드를 적극 활용하기 시작하면, 기존 명시적 필드와의 일관성 유지 부담
- 향후 MCP 전환시 scores 필드를 primary로 전환하고 명시적 필드를 deprecated로 마킹하는 추가 작업 필요

### Follow-ups
- MCP 서버 전환 시점에 명시적 필드 deprecation 계획 수립
- LLM 전략 플래닝의 비용/품질 모니터링 체계 구축
- 추가 벤치마크 라이브러리 확장 (Phase 5 실증 결과 기반)

---

## 추정 작업량

| Phase | 예상 시간 | 난이도 |
|-------|-----------|--------|
| Phase 1 | 1-2시간 | 낮음 (additive-only로 v1 대비 난이도 하향) |
| Phase 2 | 1-2시간 | 낮음 (optional 필드 추가) |
| Phase 3 | 1-2시간 | 낮음 (optional 필드 추가) |
| Phase 4 | 3-4시간 | 높음 (LLM 통합 + 동적 스키마 + demoMode) |
| Phase 5 | 1-2시간 | 낮음 (UI 업데이트 + 벤치마크 실증) |
| **합계** | **7-12시간** | |

---

## v1 -> v2 변경 요약

| 항목 | v1 | v2 | 변경 사유 |
|------|----|----|-----------|
| Phase 1 타입 전략 | `Record<string, number>` 완전 교체 | Additive-only (기존 필드 유지 + scores 추가) | Architect A-1 채택 |
| Phase 1 범위 | types.ts + scoring.ts + engine.ts + 테스트 | + types.ts(web) + orchestrator.ts CandidateCard 매핑 | Critic C-1 반영: CandidateCard 의존성 충돌 사전 방지 |
| Phase 4 LLM 위임 범위 | 전체 EvolutionStrategy (survivorCount 등 포함) | 차원/가중치/프롬프트/candidateCount만 | Architect A-2 채택 |
| 벤치마크 바이어스 처리 | 전면 제거 | demoMode 플래그로 분리 | Architect A-3 채택 |
| Phase 0 (추가 벤치마크) | 없음 | Phase 5에 통합 | Architect A-4 채택 (변형) |
| Zod 스키마 동적화 | 미명시 | Phase 4에 명시 (buildJudgeResponseSchema, buildCandidateListResponseSchema) | Critic C-2 반영 |
| candidateListSchema 동적화 | 미명시 | Phase 4에 명시 (buildCandidateListSchema) | Critic C-4 반영 |
| 테스트 수 | "기존 22개" | "기존 11개" (core 5 + web 6) | Critic C-5 반영: 실제 수치로 정정 |
| open-questions 해결 시점 | 미매핑 | Phase별 매핑 완료 | Critic C-5 반영 |
| RALPLAN-DR | 없음 | 추가 (Principles 5, Drivers 3, Options 2) | 요청 사항 |
| ADR | 없음 | 추가 (Decision, Drivers, Alternatives, Why, Consequences, Follow-ups) | 요청 사항 |
