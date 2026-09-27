"""Question categories from SKILL.md v1.6.0, Step 1.1.

Each preset fixes the scoring dimensions, their weights, the suggested threshold,
and the one-line emphasis appended to the Strict Evaluator prompt only.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class CategoryPreset:
    weights: Mapping[str, float]
    threshold: float
    evaluator_emphasis: str


def _preset(weights: dict[str, float], threshold: float, emphasis: str) -> CategoryPreset:
    return CategoryPreset(MappingProxyType(weights), threshold, emphasis)


CATEGORY_PRESETS: Mapping[str, CategoryPreset] = MappingProxyType({
    "general": _preset(
        {"logicalConsistency": 0.50, "evidenceGrounding": 0.20, "solutionUsefulness": 0.30},
        0.75,
        "Penalize internally contradictory claims and unsupported assertions.",
    ),
    "math": _preset(
        {"mathematicalRigor": 0.45, "stepValidity": 0.30, "solutionCompleteness": 0.25},
        0.80,
        "Penalize skipped steps and unjustified leaps; a correct final number with a broken proof is not high rigor.",
    ),
    "science": _preset(
        {"technicalAccuracy": 0.35, "evidenceBase": 0.30, "methodologicalSoundness": 0.20, "novelty": 0.15},
        0.75,
        "Penalize claims that outrun the cited evidence or the stated method.",
    ),
    "creative": _preset(
        {"creativity": 0.30, "originality": 0.25, "coherence": 0.25, "expressiveQuality": 0.20},
        0.70,
        "Score the named creative dimensions; do not substitute factual correctness for originality.",
    ),
    "ethical": _preset(
        {"ethicalAlignment": 0.30, "stakeholderConsideration": 0.25, "practicalFeasibility": 0.25, "argumentBalance": 0.20},
        0.75,
        "Penalize missing stakeholders and one-sided framing.",
    ),
    "coding": _preset(
        {"correctness": 0.40, "efficiency": 0.20, "readability": 0.20, "edgeCaseHandling": 0.20},
        0.80,
        "Penalize code that would fail the stated edge cases even if it looks clean.",
    ),
    "analytical": _preset(
        {"accuracy": 0.35, "completeness": 0.25, "clarity": 0.25, "insightDepth": 0.15},
        0.75,
        "Penalize strong claims that the supplied evidence does not support.",
    ),
    "biomedical": _preset(
        {"evidenceCoverage": 0.30, "specificity": 0.30, "novelty": 0.20, "actionability": 0.20},
        0.75,
        "Penalize nonspecific targets and actionability that is not tied to a mechanism.",
    ),
})

# Used for caller-supplied dimensions (Category: custom / refinement).
CUSTOM_EMPHASIS = "Score only the provided dimensions; do not import a category persona."
