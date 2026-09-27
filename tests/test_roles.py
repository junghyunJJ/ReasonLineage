from reasonlineage.core import crossover_has_distinct_voices, judges_for, pick_crossover_synthesizer

ROSTER = ["claude", "codex", "gemini"]


def test_judges_exclude_the_author():
    assert judges_for("codex", ROSTER) == ["claude", "gemini"]


def test_single_backend_judges_itself():
    assert judges_for("claude", ["claude"]) == ["claude"]


def test_orchestrator_fallback_author_gets_the_whole_roster():
    assert judges_for("orchestrator", ROSTER) == ROSTER


def test_synthesizer_is_a_non_parent():
    # Blueprint figure 3: parents by claude and codex -> gemini synthesizes.
    assert pick_crossover_synthesizer(["claude", "codex"], ROSTER, ["claude", "codex"]) == "gemini"


def test_synthesizer_prefers_fewest_survivors_then_roster_order():
    roster = ["claude", "codex", "gemini", "grok"]
    assert pick_crossover_synthesizer(["claude"], roster, ["claude", "codex"]) == "gemini"
    assert pick_crossover_synthesizer(["claude"], roster, ["claude", "gemini", "grok"]) == "codex"


def test_no_synthesizer_when_every_backend_is_a_parent():
    assert pick_crossover_synthesizer(["claude", "codex"], ["claude", "codex"], []) is None


def test_distinct_voices():
    assert crossover_has_distinct_voices(["claude", "codex"])
    assert not crossover_has_distinct_voices(["claude", "claude"])
