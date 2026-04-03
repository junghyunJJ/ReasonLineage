# ReasonForge MCP Server - Work Plan v2

**Created:** 2026-04-02
**Updated:** 2026-04-02 (Architect + Critic 피드백 반영)
**Status:** Draft - Awaiting Confirmation

---

## Context

ReasonForge는 진화적 추론 엔진(`@reasonforge/core`)으로, 후보 답변을 judge/critique/mutate/crossover 사이클을 통해 진화시킨다. 현재 Next.js 웹 대시보드(`apps/web`)에서 Codex SDK 오케스트레이터를 통해 실행되지만, 외부 LLM 호스트(Claude, ChatGPT 등)가 프로그래밍 방식으로 ReasonForge 진화 사이클을 구동할 방법이 없다.

MCP(Model Context Protocol) 서버는 ReasonForge의 핵심 루프를 도구로 노출하여, MCP 호환 호스트가 단계별로 호출할 수 있게 한다. 호스트 LLM이 진화 워크플로우를 완전히 제어하면서, 모든 스코어링/피트니스 로직은 ReasonForge 내부에서 처리된다.

---

## RALPLAN-DR Summary

### Principles
1. **Core purity** -- `@reasonforge/core` 패키지는 순수하고 부작용 없는 라이브러리로 유지. MCP 서버가 감싸되 포크하지 않는다.
2. **Stateful session** -- 진화 사이클은 본질적으로 상태를 가짐(population, generation counter, scores). 서버는 도구 호출 사이에 세션 상태를 메모리에 보관해야 한다.
3. **Guided autonomy** -- `reasonforge_next_step`은 상태 + 다음 행동 제안을 반환하지만, 호스트 LLM은 제안을 무시할 수 있다.
4. **Minimal surface** -- 완전한 사이클을 허용하는 최소한의 도구만 노출. 모든 내부 함수를 1:1 미러링하지 않는다.
5. **Stdio transport** -- 로컬용 MCP 서버는 stdio 전송을 기본으로 한다(Sequential Thinking MCP처럼). HTTP 불필요.

### Decision Drivers
1. **Host LLM ergonomics** -- 도구는 명확한 이름, 간결한 설명, 잘 타입된 입출력을 가져 호스트 LLM이 혼란 없이 사용할 수 있어야 한다.
2. **Session lifecycle** -- 서버는 다중 동시 세션을 처리하고 유휴 세션을 정리해야 한다.
3. **Reuse of existing code** -- `@reasonforge/core` 내보내기(`calculateFitness`, `evaluateBenchmarkAnswer`, `createCandidate`) 및 타입을 최대한 재사용.

### Option A: Thin Wrapper (채택)
새 `packages/mcp` 패키지에 단일 `server.ts`로 6개 도구를 등록. 세션 상태는 `Map<sessionId, SessionState>`로 보관. 각 도구 호출은 `sessionId`를 받아 해당 세션에 대해 동작한다.

**Pros:**
- 최소한의 새 코드 (~400-600줄)
- `@reasonforge/core` 함수 직접 재사용
- 모킹된 judge/critique/mutate 함수로 테스트 용이
- 확립된 MCP 서버 패턴 따름 (Sequential Thinking 스타일)

**Cons:**
- Judge/critique/mutate는 단순 스코어링 함수로 제공 (내장 LLM 통합 없음; 호스트 LLM이 직접 수행)
- 서버 재시작 시 세션 미보존 (인메모리 전용)

### Option B: Full Orchestrator Port (무효화)
`apps/web/src/lib/orchestrator.ts` 로직을 MCP 서버에 포팅, Codex SDK 통합 포함.

**무효화 사유:**
- 순환 의존성 발생 (MCP 서버가 LLM을 호출해 judge하면서, LLM이 MCP 서버를 호출)
- MCP 서버에 Codex 인증 설정 필요
- MCP의 핵심은 *호스트 LLM*이 지능을 제공하고 서버는 *구조*를 제공하는 것
- Principle #4 (minimal surface) 위반

### ADR
- **Decision:** Option A -- Thin Wrapper
- **Drivers:** Host LLM ergonomics, core purity, minimal surface
- **Alternatives considered:** Option B (Full Orchestrator Port)
- **Why chosen:** 호스트 LLM이 judge/critique/mutate 로직을 직접 구동해야 한다. MCP 서버의 역할은 인구 상태 관리, 피트니스 계산, 진화 구조 강제, 상태 보고이다.
- **Consequences:** 호스트 LLM은 세대당 여러 도구 호출을 해야 함(각 후보 점수 매기기, 선택/변이 호출). 이는 의도적 설계로 호스트에게 완전한 가시성과 제어를 부여한다.
- **Follow-ups:** v1.1에서 `core`에서 `checkTermination` 함수를 public export로 추가 검토 (Architect A3). 수요 있을 시 "auto-evolve" 배치 도구 추가 가능.

---

## Work Objectives

새 `packages/mcp` 패키지를 빌드하여 ReasonForge 진화 사이클을 6개 MCP 도구로 stdio 전송을 통해 노출한다.

---

## Tool Inventory

| Tool Name | Purpose | MCP Description (호스트 LLM에게 노출) |
|---|---|---|
| `reasonforge_next_step` | 현재 세션 상태 + 다음 행동 제안 반환 (Guided mode) | `"Call this tool FIRST to check session state and get guidance on what to do next. Returns current generation, population status, best fitness, termination status, and a suggested next action."` |
| `reasonforge_start_session` | 설정 + 시드 후보로 새 진화 세션 초기화 | `"Initialize a new ReasonForge evolution session. Provide configuration (threshold, limits, weights) and seed candidate answers. After starting, call reasonforge_next_step to see what to do."` |
| `reasonforge_score_candidate` | 후보에 대한 judge 점수 + critique 제출; 서버가 피트니스 계산 및 저장 | `"Submit judge scores and critique for a candidate. Score each dimension from 0 to 1. The server calculates fitness using weighted sum. Call reasonforge_next_step after scoring all candidates."` |
| `reasonforge_select` | 현재 인구에 대해 선택 수행 (피트니스 기준 상위 N 생존자) 후 다음 세대로 이동 | `"Run selection on the current scored population. Keeps top-N survivors by fitness and advances to the next generation. Call after all candidates are scored."` |
| `reasonforge_mutate` | 변이된 후보 제출 (호스트 LLM이 새 답변 텍스트 제공); 서버가 인구에 등록 | `"Submit a mutated candidate answer. You provide the new answer text derived from a parent candidate. The server registers it for scoring."` |
| `reasonforge_crossover` | 두 부모로부터 교차 후보 제출; 서버가 인구에 등록 | `"Submit a crossover candidate from two parent candidates. You provide the combined answer text. The server registers it for scoring."` |

---

## Guardrails

### Must Have
- 모든 6개 도구 MCP stdio 전송으로 등록 및 호출 가능
- 모든 도구 입력에 Zod 스키마 적용 (`@modelcontextprotocol/sdk`와 호환되는 `zod ^3.25 || ^4.0`)
- **[Critic #3]** scores 값 범위 검증: `z.number().min(0).max(1)` 적용. tool description에 "Score each dimension from 0 to 1" 명시
- **[Critic #1]** `calculateFitness` 호출 시 항상 dynamic path 사용: `calculateFitness({ logicalConsistency: 0, evidenceGrounding: 0, solutionUsefulness: 0 }, weights, scores)` -- 기본 3차원이든 커스텀이든 일관 동작
- **[Critic #2]** 벤치마크 미설정 세션에서 `benchmarkVerdict` 기본값: `{ passed: true, expectedAnswer: "", normalizedAnswer: "" }` -- `getDefaultBenchmarkCase()` 사용 금지 (car-wash 벤치마크가 적용되면 혼란 초래)
- 벤치마크 설정된 세션에서는 `evaluateBenchmarkAnswer` from `@reasonforge/core` 사용
- **[Critic #4]** Session TTL: 30분 idle TTL + 60초 주기 GC (`setInterval` 기반, ~15줄)
- **[Critic #5]** 각 도구의 MCP description 문자열을 위 Tool Inventory 표에 명시된 대로 제공. `reasonforge_next_step`에 "Call this tool FIRST" 패턴 사용
- `reasonforge_next_step`이 state + suggested action string 반환 (Guided mode)
- **[Architect A1]** `next_step` suggestion을 구조화: `{ suggestedTool: string, suggestedArgs?: Record<string, unknown>, explanation: string }` -- string보다 호스트 LLM이 파싱하기 용이
- **[Architect A2]** `shouldTerminate` 로컬 재구현 시 주석 명시: `// Mirrors engine.ts:27-43`
- 단위 테스트: 세션 라이프사이클, 스코어링, 선택, 종료 감지, next-step 제안, TTL GC 포함
- `package.json`에 `bin` 필드: 컴파일된 서버 엔트리 (`npx` / MCP config에서 사용)

### Must NOT Have
- HTTP/SSE 전송 없음 (v1은 stdio만)
- 내장 LLM 호출 없음 (이 패키지에 Codex SDK 의존성 없음)
- 영속 계층 없음 (인메모리 세션만)
- `@reasonforge/core` export 수정 없음. `shouldTerminate` 로직 필요 시 동일 public 입력(fitness >= threshold + optional benchmark pass)으로 로컬 재구현
- `apps/web` 또는 `packages/codex` 변경 없음

---

## Task Flow

```
[Step 1: Scaffold] --> [Step 2: Session + State + TTL] --> [Step 3: Core Tools] --> [Step 4: Next Step] --> [Step 5: Tests + Wiring]
```

---

## Detailed TODOs

### Step 1: Scaffold `packages/mcp`

패키지 구조 생성:

```
packages/mcp/
  package.json          -- name: @reasonforge/mcp, bin: ./dist/index.js
  tsconfig.json         -- extends ../../tsconfig.base.json
  src/
    index.ts            -- 엔트리 포인트: MCP 서버 생성, 도구 등록, stdio 연결
    session.ts          -- SessionState 타입, 세션 스토어 (Map), 세션 헬퍼, TTL GC
    tools.ts            -- 6개 도구 핸들러
    schemas.ts          -- 각 도구의 Zod 입출력 스키마
    termination.ts      -- shouldTerminate 로컬 재구현
  tests/
    session.test.ts
    tools.test.ts
```

**Acceptance criteria:**
- `packages/mcp/package.json` 존재. `@modelcontextprotocol/sdk`와 `@reasonforge/core` 의존성, `zod` peer 의존성
- `tsconfig.json`이 base를 확장하고 `dist/`로 컴파일
- `pnpm install` 워크스페이스 루트에서 성공
- 패키지가 `pnpm-workspace.yaml`에 참조 (`packages/*` glob으로 이미 커버)

### Step 2: Session State Management + TTL GC (`session.ts`)

인메모리 세션 스토어 구현:

```typescript
type SessionConfig = {
  threshold: number;
  populationLimit: number;
  generationLimit: number;
  weights: JudgeWeights;
  benchmark?: BenchmarkCase;  // undefined이면 벤치마크 미사용
};

type SessionState = {
  id: string;
  config: SessionConfig;
  generation: number;
  population: ScoredCandidate[];   // 현재 점수 매겨진 인구
  pendingCandidates: Candidate[];  // 제출됐지만 아직 점수 미매겨진
  events: EvolutionEvent[];
  status: "scoring" | "selecting" | "mutating" | "completed" | "failed";
  createdAt: number;
  lastAccessedAt: number;  // [Critic #4] TTL 추적용
};
```

핵심 함수:
- `createSession(config, seedCandidates)` -- `sessionId` 반환
- `getSession(sessionId)` -- `SessionState | null` 반환, 접근 시 `lastAccessedAt` 갱신
- `updateSession(sessionId, updater)` -- 원자적 업데이트
- `deleteSession(sessionId)` -- 정리

**[Critic #4] TTL GC 구현 (~15줄):**
```typescript
const SESSION_TTL_MS = 30 * 60 * 1000;  // 30분
const GC_INTERVAL_MS = 60 * 1000;       // 60초

export function startSessionGC(store: Map<string, SessionState>): NodeJS.Timeout {
  return setInterval(() => {
    const now = Date.now();
    for (const [id, session] of store) {
      if (now - session.lastAccessedAt > SESSION_TTL_MS) {
        store.delete(id);
      }
    }
  }, GC_INTERVAL_MS);
}
```

**Acceptance criteria:**
- `createSession`이 고유 세션 ID를 반환하고 초기 상태 저장
- `getSession`이 알 수 없는 ID에 null 반환
- 세션이 독립적 (두 동시 세션이 간섭하지 않음)
- `lastAccessedAt`이 모든 세션 접근 시 갱신
- TTL 만료 세션이 GC에 의해 제거 (테스트에서 짧은 TTL로 검증)

### Step 3: Core Tool Handlers (`tools.ts` + `schemas.ts` + `termination.ts`)

5개 핵심 도구 구현: `start_session`, `score_candidate`, `select`, `mutate`, `crossover`.

**`termination.ts` -- shouldTerminate 로컬 재구현:**
```typescript
// Mirrors engine.ts:27-43
// core에서 export하지 않으므로 동일 로직을 public 입력으로 재구현
export function shouldTerminate(
  bestFitness: number,
  threshold: number,
  benchmarkPassed: boolean | null  // null = 벤치마크 미설정
): boolean {
  let met = bestFitness >= threshold;
  if (benchmarkPassed !== null) {
    met = met && benchmarkPassed;
  }
  return met;
}
```

**`schemas.ts` -- [Critic #3] scores 값 범위 검증:**
```typescript
// 모든 score 차원에 0-1 범위 강제
const scoreValueSchema = z.number().min(0).max(1);

const scoresSchema = z.record(z.string(), scoreValueSchema)
  .refine(
    (scores) => Object.keys(scores).length >= 1,
    { message: "At least one score dimension is required" }
  );
```

**`reasonforge_start_session`**
- Input: `{ threshold, populationLimit, generationLimit, weights?, benchmark?, candidates: Array<{id, answer}> }`
- 세션 생성, 시드 후보를 pending(미점수)으로 저장
- Returns: `{ sessionId, candidateCount, message: "Score each candidate using reasonforge_score_candidate" }`

**`reasonforge_score_candidate` -- [Critic #1, #2, #3] 반영**
- Input: `{ sessionId, candidateId, scores: Record<string, number>, critique: string[] }`
- **[Critic #3]** 입력 검증: 모든 score 값이 0-1 범위 (Zod 스키마 `z.number().min(0).max(1)`)
- **[Critic #1]** 피트니스 계산: 항상 dynamic path 사용
  ```typescript
  const fitness = calculateFitness(
    { logicalConsistency: 0, evidenceGrounding: 0, solutionUsefulness: 0 },
    session.config.weights,
    scores  // dynamic path -- 기본 3차원이든 커스텀이든 일관 동작
  );
  ```
- **[Critic #2]** 벤치마크 처리:
  - 세션에 benchmark 설정됨: `evaluateBenchmarkAnswer(session.config.benchmark, candidate.answer)`
  - 세션에 benchmark 미설정: `{ passed: true, expectedAnswer: "", normalizedAnswer: "" }` 기본 통과 verdict 사용
  - `getDefaultBenchmarkCase()` 절대 사용 금지 (car-wash 벤치마크 적용 방지)
- `ScoredCandidate`로 인구에 저장
- Returns: `{ candidateId, fitness, benchmarkPassed, populationScoredCount, totalPending }`

**`reasonforge_select`**
- Input: `{ sessionId, survivorCount? }`
- 인구를 피트니스 내림차순 정렬, 상위 N 유지
- 세대 카운터 증가
- Returns: `{ generation, survivors: Array<{id, fitness}>, eliminated: Array<{id, fitness}> }`

**`reasonforge_mutate`**
- Input: `{ sessionId, parentId, candidateId, answer }`
- 새 후보를 pending에 등록 (호스트 LLM이 변이된 답변 텍스트 제공)
- Returns: `{ candidateId, parentId, message: "Score this candidate using reasonforge_score_candidate" }`

**`reasonforge_crossover`**
- Input: `{ sessionId, parentIds: [string, string], candidateId, answer }`
- mutate와 동일하되 부모 2개 기록
- Returns: `{ candidateId, parentIds, message: "Score this candidate using reasonforge_score_candidate" }`

**Acceptance criteria:**
- 각 도구가 Zod 스키마로 입력 검증하고 구조화된 JSON 반환
- 잘못된 sessionId는 명확한 에러 반환
- `score_candidate`에서 알 수 없는 candidateId는 에러 반환
- `select`에서 점수 매겨진 후보 없으면 에러 반환
- **[Critic #1]** 피트니스 값이 `calculateFitness` dynamic path와 일치
- **[Critic #2]** 벤치마크 미설정 세션에서 `benchmarkVerdict.passed`가 항상 `true`
- **[Critic #3]** 0-1 범위 밖 점수 제출 시 Zod 검증 에러 반환

### Step 4: Guided Next Step Tool (`reasonforge_next_step`) -- [Critic #5, Architect A1] 반영

**`reasonforge_next_step`**
- Input: `{ sessionId }`
- 현재 상태 스냅샷 + **[Architect A1] 구조화된 제안** 반환:

```typescript
{
  sessionId: string;
  generation: number;
  populationSize: number;
  pendingCount: number;        // 미점수 후보
  bestFitness: number | null;
  bestCandidateId: string | null;
  thresholdMet: boolean;
  benchmarkPassed: boolean | null;   // null if 벤치마크 미설정
  generationLimitReached: boolean;
  status: string;
  suggestion: {                      // [Architect A1] 구조화된 제안
    suggestedTool: string;           // e.g., "reasonforge_score_candidate"
    suggestedArgs?: Record<string, unknown>;  // e.g., { sessionId, candidateId }
    explanation: string;             // 사람이 읽을 수 있는 설명
  };
}
```

제안 로직 (Guided mode):
1. `pendingCount > 0` --> `{ suggestedTool: "reasonforge_score_candidate", suggestedArgs: { sessionId, candidateId: <첫 pending 후보 ID> }, explanation: "Score the N pending candidates using reasonforge_score_candidate" }`
2. 모두 점수 매겨짐 + 임계치 미달 + generation < limit --> `{ suggestedTool: "reasonforge_select", suggestedArgs: { sessionId }, explanation: "Run selection to pick survivors, then submit mutations" }`
3. 임계치 달성 --> `{ suggestedTool: "", explanation: "Threshold met. The best answer is: [candidateId] with fitness [X]. Session complete." }`
4. 세대 한도 도달 --> `{ suggestedTool: "", explanation: "Generation limit reached. Best answer: [candidateId] with fitness [X]. Consider human review." }`

**[Architect A2]** 종료 판단 시 `shouldTerminate` (termination.ts) 사용, 주석에 `// Mirrors engine.ts:27-43` 명시.

**Acceptance criteria:**
- 유효한 세션에 대해 정확한 상태 반환
- 세션 단계에 따라 suggestion 객체가 변경
- `suggestedTool` 필드가 실제 MCP 도구 이름과 일치
- `thresholdMet`이 정확히 반영: fitness >= threshold AND (벤치마크 설정 시 benchmark 통과)
- 커스텀 weights와 동적 차원에서 정상 동작

### Step 5: Server Wiring + Tests

**서버 엔트리 (`index.ts`):**
- `@modelcontextprotocol/sdk`에서 `McpServer` 생성
- 6개 도구를 이름, description, 입력 스키마 (Zod), 핸들러로 등록
- **[Critic #5]** 각 도구의 description은 Tool Inventory 표에 명시된 문자열 사용
- `StdioServerTransport`로 연결
- `#!/usr/bin/env node` shebang 추가 (bin 사용)
- **[Critic #4]** `startSessionGC()` 호출하여 TTL GC 시작

**Tests:**
- `session.test.ts`: 세션 CRUD, 동시 세션, 알 수 없는 세션 에러, **TTL GC 동작 검증** (짧은 TTL로 만료 확인)
- `tools.test.ts`:
  - 전체 사이클 테스트 (start -> score -> select -> mutate -> score -> next_step에서 threshold_met 확인)
  - **[Critic #1]** calculateFitness dynamic path 검증: 커스텀 차원만 사용하는 세션에서 피트니스 정확성
  - **[Critic #2]** 벤치마크 미설정 세션에서 benchmarkVerdict 기본값 검증
  - **[Critic #3]** 0-1 범위 밖 점수 거부 검증
  - Edge cases: 빈 인구 select, 동일 후보 이중 score, 잘못된 scores
  - **[Architect A1]** next_step suggestion 구조화 객체 검증

**워크스페이스 통합:**
- `package.json`에 `"test": "vitest run"`, `"build": "tsc"` 스크립트 추가
- 루트에서 `pnpm test` 실행 시 MCP 테스트 포함
- `tsconfig.base.json`에 `@reasonforge/mcp` 경로 매핑 추가

**Acceptance criteria:**
- `pnpm --filter @reasonforge/mcp test` 모든 테스트 통과
- `pnpm --filter @reasonforge/mcp build`가 `dist/index.js` 생성
- `node dist/index.js`로 서버 시작 시 에러 없음 (stdio 연결, MCP 메시지 대기)
- 전체 진화 사이클 테스트: 3 후보로 세션 시작 -> 모두 점수 -> 2개 선택 -> 최고 변이 -> 변이 점수 -> next_step에서 threshold_met 반환

---

## Success Criteria

1. 호스트 LLM(예: Claude)이 MCP 서버를 config에 등록하면 6개 도구가 보임
2. 호스트가 완전한 진화 사이클 구동 가능: seed -> score -> select -> mutate -> score -> 상태 확인
3. `reasonforge_next_step`이 각 단계에서 정확한 상태와 **구조화된 제안**을 제공
4. 모든 피트니스 계산이 `@reasonforge/core` 동작과 일치 (동적 차원, 커스텀 weights 포함)
5. 기존 패키지 (`core`, `codex`, `web`) 변경 없음
6. 모든 테스트 통과, 빌드 성공
7. **[Critic #3]** 점수 입력이 0-1 범위로 검증됨
8. **[Critic #2]** 벤치마크 미설정 세션이 정상 동작 (기본 통과 verdict)
9. **[Critic #4]** 30분 idle 세션이 GC에 의해 자동 정리

---

## Critic/Architect 피드백 추적표

| # | 출처 | 심각도 | 내용 | 해결 | 반영 위치 |
|---|------|--------|------|------|----------|
| 1 | Critic | Critical | `calculateFitness` 호출 매핑 -- `CandidateJudgeResult`(3필수필드) vs `scores: Record<string,number>` 불일치 | 항상 dynamic path 사용: `calculateFitness({lC:0, eG:0, sU:0}, weights, scores)` | Step 3 score_candidate |
| 2 | Critic | Critical | 벤치마크 미설정 시 `benchmarkVerdict` 처리 | `{ passed: true, expectedAnswer: "", normalizedAnswer: "" }` 기본값. `getDefaultBenchmarkCase()` 사용 금지 | Step 3 score_candidate |
| 3 | Critic | Critical | scores 값 범위 검증 누락 | Zod `z.number().min(0).max(1)` + tool description에 "Score each dimension from 0 to 1" | Step 3 schemas.ts |
| 4 | Critic | Medium | Session TTL v1 결정 | 30분 idle TTL + 60초 GC, `setInterval` 기반 (~15줄) | Step 2 session.ts |
| 5 | Critic | Medium | MCP tool description 문자열 미제공 | 각 도구에 description 예시 포함, `next_step`에 "Call this tool FIRST" | Tool Inventory 표 |
| A1 | Architect | Recommended | `next_step` suggestion 구조화 | `{ suggestedTool, suggestedArgs?, explanation }` 객체로 | Step 4 |
| A2 | Architect | Recommended | `shouldTerminate` 재구현 주석 | `// Mirrors engine.ts:27-43` 명시 | Step 3 termination.ts |
| A3 | Architect | v1.1 Roadmap | core에서 `checkTermination` export | ADR Follow-ups에 기록 | ADR |

---

## v1.1 Roadmap (비구현, 참고용)

- `@reasonforge/core`에서 `checkTermination` (현재 `shouldTerminate`) 함수를 public export으로 추가 (Architect A3)
- "auto-evolve" 배치 도구: 한 번의 호출로 전체 세대 처리
- HTTP/SSE 전송 옵션 추가
- 세션 영속화 (optional file/DB backend)
