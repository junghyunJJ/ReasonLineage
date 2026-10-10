# ALS 다이어그램 생성 프롬프트 — 2026-10-07

모드: 내장 image_gen. 전체 흐름도와 상세 계보를 새로 생성했고 상세 계보의 연결선만 두 번 수정했다. 선택한 최종 파일은 전체 흐름도 v1과 상세 계보 v3이다. 기존 이미지를 덮어쓰지 않았다.

최종 전체 흐름도: 2026-10-07-als-full-workflow-v1.png
최종 상세 계보: 2026-10-07-als-evolution-detail-v3.png

## 전체 흐름도 — 생성

Use case: infographic-diagram.
Asset type: a high resolution Korean scientific workflow infographic for a real ALS model-comparison experiment, landscape 3:2. New image, not an edit.
Primary request: make the whole procedure immediately understandable, with exceptionally readable large scores. White background, restrained teal/violet/blue model colors and amber for the selected hypothesis. Clean flat editorial diagram, abundant spacing, no illustrative neurons, no decorative pictures. Korean sans-serif text, crisp exact numbers.

Title verbatim: "ALS 실험의 전체 흐름"
Subtitle verbatim: "2026-10-07 · GPT + Grok + GLM Flash · 완료"
Top small model legend: "GPT 6.1", "Grok 4.7", "GLM 5.3 Flash".

Top horizontal 3-box pipeline:
"① 공통 질문·문헌" with "ALS 질문 + 동결 문헌 S1–S4";
arrow to "② 초기 가설 4개" with "GPT 2개 · Grok 1개 · GLM 1개";
arrow to "③ 다른 모델 2개의 비판·평가" with "작성자는 자기 가설 평가에서 제외".

Middle main section label "④ 선택 → 개선·결합 → 재평가 (3라운드)".
Show exactly four generation columns linked by forward arrows:
"초기 g0": "가설 4개 + 비판 8건", very large "0.8255", smaller "최고: c004 · GPT".
"1라운드 g1": "새 가설 2개 + 비판 4건", very large "0.8450", smaller "최고: c006 · Grok".
"2라운드 g2": "새 가설 2개 + 비판 4건", very large "0.8450", smaller "c006 유지".
"3라운드 g3": "새 가설 2개 + 비판 4건", very large "0.8450", smaller "c006 유지".
These are best-so-far INTERNAL scores; do not invent candidate scores. The three 0.8450 values are the SAME retained hypothesis, not different generated answers. Caption directly under this section: "숫자 = 해당 단계까지의 내부 최고 점수 (0–1)".
Amber outcome bar below: "최종 선택: c006 · 1라운드 결합 가설" and large "0.8255 → 0.8450   (+0.0195)".
One compact totals strip: "가설 10개 · 비판 20건 · 생성·평가 호출 30회 · 생성 27분 13초".

Lower section label "⑤ 독립 평가와 기존 단독 모델 비교".
Explain in one concise line: "DeepSeek V4.1 Flash · 익명 가설 7개 · 정방향·역방향 2회".
Four small rows, exact values, clearly separate scale from internal scores:
header "참고 평균 /5 | 초기 → 최종"
"다중 모델     3.7 → 3.9"
"GPT 단독      3.6 → 3.6"
"Grok 단독     3.3 → 4.2"
"GLM 단독      3.5 → 4.0"
Caption: "5항목·2순서의 설명용 평균 · 독립 반복 실험 아님".
Footer two clear status badges:
"전문가 평가: 대기"
"사용량 ±10% 기준: 0/3 충족 · 우위 미확정"
Separate small gray status badge, not connected as a participating model:
"Opus 재확인: [bio] 차단 · 가설 생성 안 됨"

Constraints: reproduce all scores and counts exactly, no fabricated Opus scores, no Opus participating arrow, no claim of superiority, no mixing 0–1 internal scale with /5 held-out scale, no fake laboratory outcomes. Use readable type and clear hierarchy. Spell GLM, GPT, Grok, DeepSeek, and Opus exactly.

## 상세 계보 — 최초 생성

Use case: infographic-diagram.
Asset type: a new high resolution landscape Korean scientific genealogy diagram, 3:2. White background, exceptionally readable big four-decimal scores, clear four-column grid, modern Korean sans-serif, no illustrations, no decoration.
Title verbatim: "ALS 진화 계보: 가설 10개의 생성과 선택"
Subtitle verbatim: "4개 초기 가설 + 3라운드 × 2개 새 가설 · 2026-10-07"
Legend: GPT = teal, Grok = violet, GLM Flash = blue; amber outline = selected final answer. Large score numerals are the visual priority.
Column headings:
"g0 · 초기" / "비판 8건 · 생성·평가 12회"
"g1 · 1라운드" / "비판 4건 · 생성·평가 6회"
"g2 · 2라운드" / "비판 4건 · 생성·평가 6회"
"g3 · 3라운드" / "비판 4건 · 생성·평가 6회"

Exactly ten hypothesis cards. Arrange four cards in the g0 column and two cards in each of g1,g2,g3. Each card has model/ID, huge exact fitness, operator, and an explicit parent-ID line. Do not omit parent-ID text even if drawing connectors. Exact card contents:
g0:
"c001 · GPT" / "0.8095" / "초기 가설"
"c002 · Grok" / "0.7765" / "초기 가설"
"c003 · GLM Flash" / "0.7825" / "초기 가설"
"c004 · GPT" / "0.8255" / "초기 최고"
g1:
"c005 · GPT" / "0.7940" / "개선" / "부모: c004"
"c006 · Grok" / "0.8450" / "결합" / "부모: c004 + c003" / prominent amber badge "최종 선택"
g2:
"c007 · Grok" / "0.8095" / "개선" / "부모: c006"
"c008 · GLM Flash" / "0.8230" / "결합" / "부모: c006 + c004"
g3:
"c009 · Grok" / "0.8185" / "개선" / "부모: c006"
"c010 · GLM Flash" / "0.8215" / "결합" / "부모: c006 + c004"

Critical parent topology: draw exactly these NINE solid parent-to-child connectors, with arrowheads ending at the CHILD:
1 c004→c005
2 c004→c006
3 c003→c006
4 c006→c007
5 c006→c008
6 c004→c008
7 c006→c009
8 c006→c010
9 c004→c010
Route long connectors through empty margins or small shared buses with clear labels to avoid overlap with text. This is a genealogy with retained old parents: g3 children are NOT descendants of g2 children. NEVER draw c007→c009, c008→c010, or c005→c007. c001 and c002 have NO offspring. Never assume adjacent columns imply parenting.

At bottom a distinct amber best-so-far strip, separate from the ten cards:
label "단계별 내부 최고"
four aligned values: "0.8255" then "0.8450" then "0.8450" then "0.8450", joined by simple arrows.
beneath the four values: "c004" then "c006" then "c006 유지" then "c006 유지".
A final concise explanation: "g2·g3 새 가설이 기존 최고를 넘지 못해 g1의 c006을 최종 선택".
Footer: "내부 점수 0–1 · 각 가설은 작성자가 아닌 2개 모델이 평가 · 과학적 검증 결과 아님"

Constraints: ALL ten scores and IDs exact, exactly four initial cards and two per later round, exactly nine genealogical arrows with the explicit source/child list above, distinguish hypotheses from best-so-far summary strip, no Opus nodes or invented results, no extra edges, no fabricated clinical outcomes. Keep every label legible.

## 상세 계보 — 첫 연결선 수정

Use case: precise-object-edit.
Edit target: the attached Korean ALS genealogy diagram.
Change ONLY the genealogy connector layer (lines, arrowheads, and their nearby edge labels). Preserve the title, four column headers, all ten card positions, every card's model/ID, every score, all parent-ID text, all colors and fonts, the c006 final-selection badge, best-so-far footer, and white background EXACTLY. No text or number changes.

Make these THREE precise connector corrections:
1. REMOVE the blue horizontal connector that leaves the RIGHT edge of c008 and goes to c010. Neither c007 nor c008 has any offspring. There must be NO arrows leaving either g2 card.
2. The long blue line starting at c004 and labeled "c004 → c008" currently incorrectly ends at c010. Redirect ONLY its destination so it truly ends with an arrowhead at the BOTTOM edge of c008. Keep its true source c004 and its label "c004 → c008".
3. The curved blue line starting at c006 that currently curls into the BOTTOM edge of c008 must instead end at c010. Route it beneath c008, without touching the c008 card, to the LEFT LOWER edge of c010. Label it "c006 → c010". c008 already has the correct horizontal direct c006→c008 line; remove the duplicate c006→c008 bottom entry by this redirect.

Keep these SEVEN already-correct connectors:
c004→c005, c004→c006, c003→c006, c006→c007, c006→c008 (the direct horizontal one), c006→c009 (purple long route), c004→c010 (teal long bottom route).
Add no other connectors. Final diagram must have EXACTLY NINE genealogical arrows:
c004→c005; c004→c006; c003→c006; c006→c007; c006→c008; c004→c008; c006→c009; c006→c010; c004→c010.
Never draw any outgoing line from c001,c002,c005,c007,c008,c009,c010. No line may travel through any hypothesis card or visually seem to originate from a card it merely passes. Use two separated lower margin lanes for the redirected c004→c008 and c006→c010 lines. All sources, labels, and arrowheads must agree. Preserve all correct typography and layout.

## 상세 계보 — 최종 연결선 수정

Edit only the TWO LOWER BLUE CURVED arrows in this diagram. Their STARTING POINTS are currently swapped. Keep their destination cards and all text/cards/scores unchanged.

Required corrected short blue curved arrow: START at c004 (bottom-left GPT 0.8255), END at the bottom of c008 (GLM Flash 0.8230). Label "c004 → c008". It must NOT start at c006.
Required corrected long blue curved arrow: START at c006 (gold-bordered Grok 0.8450), END at the bottom-left of c010 (GLM Flash 0.8215). Label "c006 → c010". It must NOT start at c004.

Remove the existing c006→c008 bottom-entry curve and the existing c004→c010 BLUE long curve, and replace them by the two correct source/destination pairs above. Use two separated paths below the cards. Neither curve should touch or pass through another card. Show a gap where unrelated wires cross.

Preserve all SEVEN other connectors, including the TEAL c004→c010 bottom route, the direct horizontal BLUE c006→c008 line, and both purple routes from c006. Preserve every score, number, parent-ID label, title, column header, footer, layout and card color. There must be exactly nine parent edges. This is ONLY a starting-point swap for these two blue arrows.

원자료와 그림의 점수·부모 관계를 대조한 기록: 2026-10-07-als-diagram-verification.json
Opus 단일 재확인 기록: ../evidence/2026-10-07-opus-recheck/status.json

