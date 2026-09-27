"""Deterministic core: no model calls, no I/O except the lineage log."""

from .categories import CATEGORY_PRESETS, CUSTOM_EMPHASIS, CategoryPreset
from .fitness import composite_fitness, judge_spread, median_scores, normalize_weights
from .lineage import LineageLog
from .models import OPERATORS, Candidate, JudgeScore
from .roles import crossover_has_distinct_voices, judges_for, pick_crossover_synthesizer
from .selection import SelectionResult, select_survivors
from .state import EvolutionConfig, EvolutionState, Status, Termination

__all__ = [
    "CATEGORY_PRESETS",
    "CUSTOM_EMPHASIS",
    "OPERATORS",
    "Candidate",
    "CategoryPreset",
    "EvolutionConfig",
    "EvolutionState",
    "JudgeScore",
    "LineageLog",
    "SelectionResult",
    "Status",
    "Termination",
    "composite_fitness",
    "crossover_has_distinct_voices",
    "judge_spread",
    "judges_for",
    "median_scores",
    "normalize_weights",
    "pick_crossover_synthesizer",
    "select_survivors",
]
