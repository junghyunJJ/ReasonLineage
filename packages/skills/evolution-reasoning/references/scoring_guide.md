# Scoring Guide for Evolution Reasoning

## Calibration Bands

Use these anchors consistently across all dimensions:

| Score Range | Label | Meaning | Justification Required? |
|-------------|-------|---------|------------------------|
| 0.90 - 1.00 | Excellent | Genuinely outstanding. Specific evidence supports this. | YES — must cite what makes it exceptional |
| 0.70 - 0.89 | Good | Clearly above average with minor issues. | Brief note on what's strong |
| 0.50 - 0.69 | Acceptable | Meets minimum bar but has notable weaknesses. | Note the weaknesses |
| 0.30 - 0.49 | Weak | Significant problems that need addressing. | List specific problems |
| 0.00 - 0.29 | Poor | Fundamentally flawed or missing. | Explain what's wrong or absent |

**The default score for an "okay" item should be around 0.6, not 0.8.** Most items are acceptable, not good. Reserve high scores for genuinely strong work.

---

## Common Pitfalls

### 1. Score Inflation

**What it is**: Giving 0.8+ to items that are merely acceptable.

**Why it happens**: LLMs tend to rate their own outputs favorably. "This seems reasonable" becomes 0.85.

**How to avoid**: Before assigning a score above 0.8, ask: "What specific evidence makes this better than average?" If you can't name concrete strengths, lower the score to 0.6-0.7.

### 2. Score Compression

**What it is**: All items score between 0.7-0.8 regardless of actual quality differences.

**Why it happens**: Reluctance to give very high or very low scores.

**How to avoid**: Force spread. At least one item should score below 0.5 on at least one dimension. If all items look similar, the dimensions may be too coarse — consider subdividing.

### 3. Confirmation Bias

**What it is**: Rating items higher because they align with what you would have generated.

**Why it happens**: Same-model self-critique inherently favors similar reasoning patterns.

**How to avoid**: Score each dimension independently. Ask "Is the evidence actually there?" rather than "Does this sound right?" Focus on what's verifiable, not what's plausible.

### 4. Dimension Conflation

**What it is**: Letting one dimension's score bleed into another. A well-written item gets high "accuracy" even when the accuracy is unverified.

**Why it happens**: Halo effect — a strong impression in one area lifts all scores.

**How to avoid**: Score dimensions in isolation. Cover the other dimension scores when evaluating each one. Ask the dimension-specific question only.

### 5. Cross-Generation Calibration Drift

**What it is**: Scores creep upward across generations, even when actual quality plateaus. Gen-0 items score 0.60, gen-2 items score 0.78 despite similar actual quality.

**Why it happens**: As the agent sees its own prior scores and improvements in context, it anchors on those numbers and adjusts upward. Familiarity breeds favorable scoring.

**How to avoid**: Before scoring each new generation, re-state the gen-0 best score as an anchor. Ask: "Would this new candidate genuinely score X if I saw it fresh, without knowing the evolutionary history?" If you cannot identify specific, concrete improvements over the previous generation's best, the score should not increase.

---

## Domain-Specific Scoring Examples

### General Reasoning (default dimensions)

| Dimension | 0.3 (Weak) | 0.6 (Acceptable) | 0.9 (Excellent) |
|-----------|-----------|------------------|-----------------|
| Logical Consistency | Contains contradictions or unsupported logical leaps | Reasoning follows logically but with minor gaps | Airtight reasoning with each step explicitly supported |
| Evidence Grounding | Claims made without any supporting evidence | Some major claims backed by evidence or examples | All major claims cite specific, verifiable evidence |
| Solution Usefulness | Impractical, off-topic, or too vague to act on | Addresses the question adequately with reasonable suggestions | Directly actionable with concrete steps, tools, or methods |

### Hypotheses (e.g., drug-target-hypothesis)

| Dimension | 0.3 (Weak) | 0.6 (Acceptable) | 0.9 (Excellent) |
|-----------|-----------|------------------|-----------------|
| Evidence Coverage | Cites 1 evidence file | Cites 2-3 files with specific findings | Cites 4+ files with quantitative data points |
| Specificity | Vague prediction ("X may affect Y") | Named intervention + measurable outcome | Named intervention + outcome + model system + failure criterion |
| Novelty | Restates known biology | Combines known elements in a new way | Identifies unexpected connection from the data |
| Actionability | No clear experimental path | Feasible experiment identified | Specific protocol with controls and readouts |

### Research Questions

| Dimension | 0.3 (Weak) | 0.6 (Acceptable) | 0.9 (Excellent) |
|-----------|-----------|------------------|-----------------|
| Clarity | Ambiguous scope | Clear but broad | Precisely bounded with defined terms |
| Feasibility | Requires unavailable resources | Doable with significant effort | Achievable with existing tools and data |
| Impact | Incremental confirmation | Useful practical knowledge | Could change current understanding or practice |

### Experimental Designs

| Dimension | 0.3 (Weak) | 0.6 (Acceptable) | 0.9 (Excellent) |
|-----------|-----------|------------------|-----------------|
| Internal Validity | Missing controls | Appropriate controls identified | Controls + confounders + blinding addressed |
| Statistical Power | No sample size justification | Reasonable N with basic justification | Power analysis with effect size estimates |
| Reproducibility | Key details omitted | Methods section present | Full protocol with reagents, settings, and code |

### Math (math category)

| Dimension | 0.3 (Weak) | 0.6 (Acceptable) | 0.9 (Excellent) |
|-----------|-----------|------------------|-----------------|
| Mathematical Rigor | Contains logical errors or unjustified steps | Reasoning is correct but missing some justifications | Every step is rigorously justified with no gaps |
| Step Validity | Multiple steps are incorrect or skipped | Steps are mostly valid with minor omissions | Each step follows necessarily from the previous |
| Solution Completeness | Answer is partial or missing key cases | Main case solved but edge cases not addressed | Complete solution covering all cases with verification |

### Coding (coding category)

| Dimension | 0.3 (Weak) | 0.6 (Acceptable) | 0.9 (Excellent) |
|-----------|-----------|------------------|-----------------|
| Correctness | Fails on basic inputs or has logic errors | Works for typical inputs but fails edge cases | Handles all inputs correctly including edge cases |
| Efficiency | Brute force or unnecessarily complex (e.g., O(n³) when O(n log n) exists) | Reasonable complexity but not optimal | Optimal or near-optimal time and space complexity |
| Readability | Unclear variable names, no structure, hard to follow | Reasonably organized but could be cleaner | Clean, well-named, self-documenting code |
| Edge Case Handling | No consideration of edge cases | Some edge cases handled (null, empty) | Comprehensive: null, empty, overflow, concurrency, etc. |

### Creative (creative category)

| Dimension | 0.3 (Weak) | 0.6 (Acceptable) | 0.9 (Excellent) |
|-----------|-----------|------------------|-----------------|
| Creativity | Relies on clichés and obvious approaches | Some fresh elements mixed with familiar patterns | Genuinely surprising or inventive approach |
| Originality | Closely resembles existing well-known works | Familiar genre with some distinctive elements | Unique voice, perspective, or structural innovation |
| Coherence | Disjointed, contradictory, or confusing | Mostly consistent with minor inconsistencies | Fully internally consistent, every element serves the whole |
| Expressive Quality | Flat, generic language or poor craft | Competent writing with some memorable moments | Vivid, precise language that enhances meaning |

### Ethical (ethical category)

| Dimension | 0.3 (Weak) | 0.6 (Acceptable) | 0.9 (Excellent) |
|-----------|-----------|------------------|-----------------|
| Ethical Alignment | Ignores relevant ethical principles | Applies ethical frameworks but superficially | Deep engagement with relevant ethical traditions and principles |
| Stakeholder Consideration | Considers only one perspective | Identifies major stakeholders but misses some | Comprehensive mapping of all affected parties and their interests |
| Practical Feasibility | Proposed approach is unrealistic | Feasible but implementation challenges not addressed | Realistic with concrete steps and acknowledged constraints |
| Argument Balance | One-sided, dismisses opposing views | Acknowledges counterarguments but doesn't engage deeply | Steelmans opposing positions before presenting conclusion |

### Analytical (analytical category)

| Dimension | 0.3 (Weak) | 0.6 (Acceptable) | 0.9 (Excellent) |
|-----------|-----------|------------------|-----------------|
| Accuracy | Contains factual errors or misinterpretations | Mostly accurate with minor errors | All claims verified and precisely stated |
| Completeness | Covers only obvious aspects | Addresses main points but misses secondary factors | Thorough coverage including non-obvious considerations |
| Clarity | Disorganized, hard to follow the argument | Clear structure but some sections could be tighter | Crystal clear organization with effective use of evidence |
| Insight Depth | States the obvious, no deeper analysis | Some useful observations beyond surface level | Reveals non-obvious connections or implications |

### Science (science category)

| Dimension | 0.3 (Weak) | 0.6 (Acceptable) | 0.9 (Excellent) |
|-----------|-----------|------------------|-----------------|
| Technical Accuracy | Contains scientific errors or misconceptions | Scientifically sound but oversimplified | Precise, nuanced understanding of the science |
| Evidence Base | No citations or only general references | Cites relevant studies but limited in scope | Comprehensive evidence from multiple quality sources |
| Methodological Soundness | No consideration of methodology | Methods identified but limitations not discussed | Rigorous methodology with controls, limitations, and alternatives |
| Novelty | Restates textbook knowledge | Combines known elements in a useful way | Identifies genuinely new connections or approaches |

---

## Critique Writing Guide

Each critique point must be:

1. **Specific**: Name the exact weakness. Not "lacks detail" but "the mechanism connecting X to Y is not explained."

2. **Actionable**: Suggest what to do. Not "improve evidence" but "add STRING PPI score for the X-Y interaction from stage1_X--Y.json."

3. **Bounded**: One issue per point. Don't combine "weak evidence AND unclear mechanism" into one critique.

**Good critique examples**:
- "The hypothesis claims TGFB1 drives fibrosis but cites no PPI data for the TGFB1-receptor interaction. Add STRING scores from stage1_TGFB1--P4HB.json."
- "The falsifiable prediction lacks a failure criterion. Add: 'If knockout of X does not reduce Y by >50%, the hypothesis is falsified.'"
- "Evidence Coverage is low (2/8 files cited). The stage3_ICAM1.json ChEMBL data and stage1_ICAM1--EZR.json Census coexpression data are relevant but unused."

**Bad critique examples**:
- "Needs more evidence" (not specific)
- "This is a weak hypothesis" (not actionable)
- "The writing could be improved and the evidence is thin and the prediction is vague" (not bounded — three issues in one)

---

## Crossover Evaluation Guidance

When scoring candidates produced by crossover (combining two parent candidates), apply additional scrutiny:

### What Makes a Good Crossover

A successful crossover takes the **best elements from each parent** and produces a coherent, unified result. It should score higher than at least one parent on the composite fitness.

| Quality | Description | Expected Outcome |
|---------|-------------|-----------------|
| **Strong crossover** | Identifies complementary strengths, merges them into a coherent whole | Composite fitness >= best parent |
| **Adequate crossover** | Combines some strengths but misses opportunities | Composite fitness between the worst and best parent |
| **Failed crossover** | Mechanical concatenation, internal contradictions, or lost strengths | Composite fitness < worst parent |

### Common Crossover Pitfalls

1. **Mechanical concatenation**: Simply appending one parent's content to the other without integration. The result reads as two separate items stitched together. Score lower on coherence/clarity dimensions.

2. **Strength dilution**: In attempting to combine all parents, the crossover weakens what each parent did well. The risk grows with the number of parents — three-way merges drift toward a vague committee answer. Check whether the crossover retains the highest-scoring dimensions from each parent.

3. **Internal contradiction**: When parents take different approaches, merging them may introduce logical contradictions. Score lower on logicalConsistency or equivalent dimension.

4. **Loss of specificity**: Generalizing to accommodate every parent's perspective, losing the concrete details that made each parent strong. Score lower on specificity/depth dimensions.

### Scoring Crossover Candidates

When scoring a crossover candidate, explicitly compare against its contributing parents:

- For each dimension, check: does the crossover score at least as high as the best parent on this dimension?
- If the crossover scores lower than every parent on any dimension, note this in the critique as a regression.
- A crossover that fails to improve on the best parent's composite fitness should receive a critique point explaining what was lost in the merge.
- **Decomposition check**: Did the crossover candidate's generation include an explicit decomposition step (listing each parent's top strengths before writing)? If not, score lower on the weakest dimension — unstructured crossover tends to produce averaging rather than genuine synthesis.

---

## Composite Score Calculation

```
composite = sum(score[dim] * weight[dim] for dim in dimensions)
```

**Example**: dimensions = {accuracy: 0.4, clarity: 0.3, depth: 0.3}

| Dimension | Score | Weight | Contribution |
|-----------|-------|--------|-------------|
| accuracy | 0.8 | 0.4 | 0.32 |
| clarity | 0.6 | 0.3 | 0.18 |
| depth | 0.7 | 0.3 | 0.21 |
| **Composite** | | | **0.71** |

Weights must sum to ~1.0. If they don't, normalize before calculating.
