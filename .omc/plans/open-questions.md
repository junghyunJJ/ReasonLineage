# Open Questions

## reasonforge-flexibilization - 2026-04-02

### v2에서 해결된 항목

- [x] Phase 4에서 `planEvolutionStrategy`의 LLM 호출 비용/latency 예산은 얼마인가? -- **결정: 경량 모델(haiku급)로 전략 플래닝, timeout 5초, fallback 기본값** (Phase 4에서 구현)
- [x] 벤치마크 바이어스 제거 후, seeded car-wash 벤치마크를 계속 기본 데모로 유지할 것인가? -- **결정: demoMode 플래그로 분리. 데모시 demoMode=true로 유지, 실제 사용시 비활성화** (Architect A-3 채택)
- [x] `planEvolutionStrategy`가 반환하는 차원(dimensions)의 최대 개수를 제한할 것인가? -- **결정: 최대 7개로 제한** (Phase 4에서 구현)
- [x] Phase 4의 프롬프트 동적화 범위: LLM이 프롬프트 자체를 생성하게 할 것인가, 아니면 미리 정의된 템플릿 중 선택하게 할 것인가? -- **결정: LLM이 evaluationPrompt를 자유 생성 (범위 제한 내)** (Phase 4에서 구현)
- [x] 기존 DB에 저장된 런 데이터의 마이그레이션을 일괄로 할 것인가, 런타임에서 lazy하게 할 것인가? -- **결정: 런타임 lazy 마이그레이션 (migrateCandidateCard)** (Phase 5에서 구현)

### 미해결 항목

- [ ] MCP 전환 시점에서 `EvolutionStrategy`를 MCP tool parameter로 노출할 계획인가? -- Phase 2-3의 타입 설계에 영향을 줄 수 있음. 현재는 JSON-serializable하게 설계하되, 함수 타입(custom termination, sortBy function)은 string enum으로 대체 가능하게 설계.
- [ ] Additive-only 이중 구조(명시적 필드 + scores)의 deprecation 시점은 언제인가? -- MCP 전환시 scores를 primary로 승격하고 명시적 필드를 deprecated로 마킹할 예정이나, 구체적 시점 미정.
- [ ] demoMode 자동감지 레거시 경로(`prompt === defaultBenchmark.prompt`)를 언제 제거할 것인가? -- isDemoMode의 auto-detect 분기는 레거시 호환용이나, 명시적 플래그 전환이 완료되면 제거 가능.

### Critic/Architect 리뷰에서 추가된 항목

- [ ] Phase 4의 동적 Zod 스키마(`buildJudgeResponseSchema`)가 런타임에 예상치 못한 차원명(특수문자, 빈 문자열 등)을 받을 때의 방어 로직 필요 -- Phase 4 구현시 입력 검증 추가 필요.
- [ ] `planEvolutionStrategy`의 LLM 응답이 기존 3차원과 완전히 다른 차원만 반환할 경우, 기존 명시적 필드(logicalConsistency 등)에는 0이 채워지는데 이것이 의미적으로 올바른지 -- Additive-only 이중 구조의 부작용. scores 필드를 우선 사용하는 코드 경로에서만 영향.

## reasonforge-mcp-server - 2026-04-02

### v2에서 해결된 항목 (Critic/Architect 피드백 반영)

- [x] **Session TTL / cleanup policy** -- **결정: 30분 idle TTL + 60초 GC (`setInterval` 기반). v1에서 구현** (Critic #4)
- [x] **`shouldTerminate` duplication** -- **결정: `termination.ts`에 로컬 재구현, `// Mirrors engine.ts:27-43` 주석 명시. v1.1에서 core `checkTermination` export 검토** (Architect A2, A3)
- [x] **`calculateFitness` 호출 매핑** -- **결정: 항상 dynamic path 사용 `calculateFitness({lC:0, eG:0, sU:0}, weights, scores)`. 기본/커스텀 차원 일관 동작** (Critic #1)
- [x] **벤치마크 미설정 시 `benchmarkVerdict` 처리** -- **결정: `{ passed: true, expectedAnswer: "", normalizedAnswer: "" }` 기본값. `getDefaultBenchmarkCase()` 사용 금지** (Critic #2)
- [x] **scores 값 범위 검증** -- **결정: Zod `z.number().min(0).max(1)` + tool description에 "Score each dimension from 0 to 1" 명시** (Critic #3)
- [x] **MCP tool description 문자열** -- **결정: 각 도구에 description 제공. `next_step`에 "Call this tool FIRST" 패턴 사용** (Critic #5)
- [x] **`next_step` suggestion 구조화** -- **결정: `{ suggestedTool, suggestedArgs?, explanation }` 객체로 구조화** (Architect A1)

### 미해결 항목

- [ ] **Benchmark matcher limitation** -- `reasonforge_start_session`이 optional `benchmark`을 `expectedAnswer`와 함께 받지만, MCP 도구는 함수를 전송할 수 없어 커스텀 `matcher` 필드를 전달할 수 없음. v1에서는 기본 contains-matcher만 지원할 것인지, 명명된 내장 매처 세트("contains", "exact", "regex")를 지원할 것인지.
- [ ] **Max concurrent sessions** -- 메모리 문제 방지를 위해 활성 세션 수를 제한할 것인지, v1에서는 무제한으로 둘 것인지.
- [ ] **Tool naming convention** -- `reasonforge_` 접두사 사용 확정. MCP 도구 이름은 서버별 전역 범위. 더 짧은 이름(e.g., `start_session`)으로 변경 여부.
- [ ] **Zod version alignment** -- MCP SDK가 `zod ^3.25 || ^4.0` 허용. 웹 앱이 `zod@4.3.6` 사용. MCP 패키지가 동일 버전을 고정할지 SDK가 자체 해결하게 할지.

## fix-evolution-skill-high-findings - 2026-04-04

- [ ] **State block format: Markdown vs JSON** -- The structured state block in the State Management section could be defined as a markdown table, a JSON code block, or a YAML code block. JSON is more parseable if persistent mode reads it; markdown is more natural for in-model mode. Decision affects both readability and future MCP integration.
- [ ] **Benchmark matcher semantics in skill context** -- The skill doc should specify what "passes benchmark" means for an in-model agent. The code uses `evaluateBenchmarkAnswer()` which does normalized contains-matching. Should the skill doc specify "contains" matching, or leave it to the agent's judgment? Overly strict matching could cause false negatives.
- [ ] **Crossover-before-mutation or mutation-before-crossover** -- `engine.ts` does mutation first, then crossover. `handlers.ts` allows either order (both require `mutating` status). The skill doc currently says mutation then crossover. Should we enforce this order or say both happen during `mutating` phase in any order? Ordering affects whether crossover operates on original survivors or mutated offspring.
- [ ] **State block emission frequency vs context budget** -- Requiring the agent to emit a full state block after every phase transition consumes context tokens. For large populations (10+ candidates), this could be significant. Should the skill recommend abbreviated state blocks (IDs + fitness only) after routine operations, with full blocks only at generation boundaries?

## evolution-skill-review-fixes - 2026-04-04

- [ ] **`calculateFitness` overload vs breaking change** -- The plan recommends a backward-compatible overload (`calculateFitness(weights, scores)` alongside old 3-arg signature). Should the old signature be kept permanently or removed at a specific version milestone? Affects API surface cleanliness vs. upgrade friction.
- [ ] **`handleFinalizeMutations` vs auto-transition on score** -- Issue #1 fix has two approaches: (a) explicit new tool to finalize mutations, or (b) auto-transition to `scoring` when `handleScoreCandidate` is called while in `mutating` status. Plan recommends (b). Should the agent be required to signal "done mutating" explicitly for stricter protocol control, or is the implicit transition acceptable?
- [ ] **`failed` status trigger scope** -- Plan only sets `failed` when generation limit reached with zero scored population. Should other failure modes trigger it (e.g., all candidates fail benchmark, population drops to zero after selection)? More failure modes = more edge cases to test.
- [ ] **Weight normalization side effects** -- Plan says normalize weights internally in `calculateFitness`. If caller passes `{ a: 2, b: 3 }` and expects raw weighted sum (= 5.0), normalization would return ~1.0 instead. Should normalization be opt-in or always-on? Affects backward compat of fitness values.
- [ ] **Deprecated field removal timeline** -- Three deprecated fields on `ScoredCandidate` and `EvolutionEvent`. Should removal target v0.2.0 (next minor) or v1.0.0 (first stable)? Earlier removal reduces tech debt; later removal gives consumers more migration time.
- [ ] **Crossover-before-mutation or mutation-before-crossover** -- Inherited from prior review. The fix for Issue #1 now allows either order during `mutating` phase. The plan should specify whether SKILL.md continues to recommend mutation-first or says "any order during mutating phase."
