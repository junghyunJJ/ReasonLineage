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
