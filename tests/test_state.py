import pytest

from helpers import WEIGHTS, uniform
from reasonlineage.core import Candidate, EvolutionConfig, EvolutionState, JudgeScore, Status, Termination
from reasonlineage.core.state import ProtocolError, seeds_per_model


def config(**overrides):
    base = {"weights": WEIGHTS, "population_limit": 3, "survivor_count": 2, "generation_limit": 2}
    return EvolutionConfig(**{**base, **overrides})


def seeds():
    return [Candidate(f"seed-{i}", f"answer {i}", author) for i, author in enumerate(["claude", "codex", "gemini"], 1)]


def score(state, cid, value):
    return state.record_score(cid, [uniform(value, "j1")])


def test_fixed_generation_run_does_exactly_generation_limit_cycles():
    state = EvolutionState(config(early_stop=False, threshold=0.5), seeds())
    for cid, value in [("seed-1", 0.5), ("seed-2", 0.6), ("seed-3", 0.4)]:
        score(state, cid, value)
    assert state.status == Status.READY_TO_SELECT  # threshold met, but early_stop is off

    first = state.select()
    assert state.generation == 1 and state.status == Status.MUTATING
    assert [c.id for c in first.survivors] == ["seed-2", "seed-1"]
    assert state.new_candidate_slots == 1
    state.register(Candidate("mut-gen-1-1", "better", "codex", "mutation", ("seed-2",)))
    score(state, "mut-gen-1-1", 0.7)

    state.select()
    assert state.generation == 2
    state.register(Candidate("cross-gen-2", "merged", "gemini", "crossover", ("mut-gen-1-1", "seed-2")))
    score(state, "cross-gen-2", 0.75)

    assert state.select() is None
    assert state.status == Status.COMPLETED
    assert state.termination == Termination.GENERATION_LIMIT
    assert state.best.id == "cross-gen-2"
    assert state.best_history == pytest.approx([0.6, 0.7, 0.75])
    assert state.evaluations == 5
    assert state.archive["cross-gen-2"].generation == 2


def test_early_stop_completes_when_threshold_met():
    state = EvolutionState(config(threshold=0.55), seeds())
    for cid, value in [("seed-1", 0.5), ("seed-2", 0.6), ("seed-3", 0.4)]:
        score(state, cid, value)
    assert state.status == Status.COMPLETED
    assert state.termination == Termination.THRESHOLD_MET


def test_fitness_is_the_weighted_sum_of_per_dimension_medians():
    state = EvolutionState(config(), seeds()[:1])
    panel = [uniform(0.6, "codex"), uniform(0.9, "gemini"), uniform(0.7, "grok")]
    candidate = state.record_score("seed-1", panel)
    assert candidate.fitness == pytest.approx(0.7)
    assert len(candidate.judge_scores) == 3  # raw scores are kept next to the median


def test_critique_is_merged_without_duplicates():
    state = EvolutionState(config(), seeds()[:1])
    panel = [
        JudgeScore("codex", {d: 0.5 for d in WEIGHTS}, ("cite the trial", "name the target")),
        JudgeScore("gemini", {d: 0.5 for d in WEIGHTS}, ("cite the trial",)),
    ]
    assert state.record_score("seed-1", panel).critique == ["cite the trial", "name the target"]


def test_population_limit_is_enforced():
    state = EvolutionState(config(), seeds())
    for cid in ["seed-1", "seed-2", "seed-3"]:
        score(state, cid, 0.5)
    state.select()
    state.register(Candidate("mut-gen-1-1", "x", "claude", "mutation", ("seed-1",)))
    with pytest.raises(ProtocolError, match="population_limit"):
        state.register(Candidate("mut-gen-1-2", "y", "codex", "mutation", ("seed-2",)))


def test_duplicate_ids_and_unknown_parents_are_rejected():
    with pytest.raises(ProtocolError, match="duplicate"):
        EvolutionState(config(), [Candidate("seed-1", "a", "x"), Candidate("seed-1", "b", "y")])
    state = EvolutionState(config(), seeds())
    for cid in ["seed-1", "seed-2", "seed-3"]:
        score(state, cid, 0.5)
    state.select()
    with pytest.raises(ProtocolError, match="unknown parent"):
        state.register(Candidate("mut-gen-1-1", "x", "claude", "mutation", ("seed-9",)))


def test_operations_in_the_wrong_status_are_rejected():
    state = EvolutionState(config(), seeds())
    with pytest.raises(ProtocolError):
        state.select()
    with pytest.raises(ProtocolError):
        state.register(Candidate("mut-gen-0-1", "x", "claude", "mutation", ("seed-1",)))


def test_generation_with_no_new_candidates_goes_straight_back_to_selection():
    state = EvolutionState(config(generation_limit=3), seeds())
    for cid in ["seed-1", "seed-2", "seed-3"]:
        score(state, cid, 0.5)
    state.select()
    state.start_scoring()
    assert state.status == Status.READY_TO_SELECT
    assert len(state.best_history) == 2


def run_to_stagnation(recovery_fitness):
    state = EvolutionState(config(generation_limit=10), seeds())
    for cid, value in [("seed-1", 0.60), ("seed-2", 0.50), ("seed-3", 0.40)]:
        score(state, cid, value)
    for gen, value in [(1, 0.61), (2, 0.62)]:
        state.select()
        state.register(Candidate(f"mut-gen-{gen}-1", "x", "claude", "mutation", (state.best.id,)))
        score(state, f"mut-gen-{gen}-1", value)
    state.select()  # history 0.60 -> 0.61 -> 0.62: no gain above 0.02 for two generations
    assert state.recovery_due
    state.register(Candidate("recovery-gen-3", "fresh approach", "codex", "recovery"))
    assert not state.recovery_due
    score(state, "recovery-gen-3", recovery_fitness)
    return state, state.select()


def test_stagnation_ends_the_run_when_recovery_fails():
    state, result = run_to_stagnation(0.63)
    assert result is None
    assert state.termination == Termination.STAGNATION


def test_stagnation_recovery_that_improves_continues_the_run():
    state, result = run_to_stagnation(0.70)
    assert result is not None
    assert state.status == Status.MUTATING


def test_evaluation_cap_marks_the_run_failed():
    state = EvolutionState(config(max_evaluations=2), seeds())
    score(state, "seed-1", 0.5)
    score(state, "seed-2", 0.5)
    with pytest.raises(ProtocolError, match="budget"):
        score(state, "seed-3", 0.5)
    assert state.status == Status.FAILED
    assert state.termination == Termination.BUDGET_EXHAUSTED


def test_prescored_only_start_is_ready_to_select():
    items = [Candidate(f"item-{i}", "x", "external", fitness=0.5) for i in range(2)]
    state = EvolutionState(config(), prescored=items)
    assert state.status == Status.READY_TO_SELECT


@pytest.mark.parametrize("bad", [
    {"survivor_count": 3},  # no new-candidate slot left
    {"population_limit": 1, "survivor_count": 1},
    {"generation_limit": 0},
    {"threshold": 1.5},
])
def test_config_validation(bad):
    with pytest.raises(ValueError):
        config(**bad)


@pytest.mark.parametrize("n, expected", [(1, (4, 2)), (2, (4, 2)), (3, (6, 4)), (4, (4, 2)), (5, (5, 3))])
def test_for_roster_sizing(n, expected):
    cfg = EvolutionConfig.for_roster(n, WEIGHTS)
    assert (cfg.population_limit, cfg.survivor_count) == expected
    assert cfg.new_candidate_slots == 2  # one mutation and one crossover per generation
    assert cfg.generation_limit == 3
    assert (cfg.tie_margin, cfg.dominance_margin, cfg.stagnation_threshold) == (0.03, 0.03, 0.03)


@pytest.mark.parametrize("n, s", [(1, 4), (2, 2), (3, 2), (4, 1), (5, 1)])
def test_seeds_per_model(n, s):
    assert seeds_per_model(n) == s


def test_stagnation_detection_can_be_turned_off():
    state = EvolutionState(config(generation_limit=10, stagnation_recovery=False), seeds())
    for cid, value in [("seed-1", 0.60), ("seed-2", 0.50), ("seed-3", 0.40)]:
        score(state, cid, value)
    for gen, value in [(1, 0.61), (2, 0.62)]:
        state.select()
        state.register(Candidate(f"mut-gen-{gen}-1", "x", "claude", "mutation", (state.best.id,)))
        score(state, f"mut-gen-{gen}-1", value)
    assert state.select() is not None  # the same history stagnates when detection is on
    assert not state.recovery_due
