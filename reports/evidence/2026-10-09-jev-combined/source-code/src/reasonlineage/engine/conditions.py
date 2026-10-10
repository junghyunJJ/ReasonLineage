"""The two experiment axes (spec 5.8): who judges an answer, and what the judges see."""

from typing import Mapping, Sequence

from ..core.roles import judges_for
from .config import ConfigError

JUDGE_AXIS = ("recuse", "self", "same_family", "other_vendor", "all")
CONTEXT_AXIS = ("isolated", "author_label", "shared_trace")


def judge_set(axis: str, author: str, active: Sequence[str], family: Mapping[str, str]) -> list[str]:
    if axis == "recuse":
        return judges_for(author, active)
    if axis == "self":
        return [author]
    if axis == "same_family":
        return [m for m in active if m != author and family[m] == family[author]]
    if axis == "other_vendor":
        return [m for m in active if family[m] != family[author]]
    if axis == "all":
        return list(active)
    raise ConfigError(f"unknown judge axis {axis!r}; expected one of {list(JUDGE_AXIS)}")


def check_conditions(judges: str, context: str, active: Sequence[str], family: Mapping[str, str]) -> list[str]:
    """Raise ConfigError when the axes cannot run with this panel; otherwise return reliability warnings."""
    if judges not in JUDGE_AXIS:
        raise ConfigError(f"unknown judge axis {judges!r}; expected one of {list(JUDGE_AXIS)}")
    if context not in CONTEXT_AXIS:
        raise ConfigError(f"unknown context {context!r}; expected one of {list(CONTEXT_AXIS)}")
    alone = [author for author in active if not judge_set(judges, author, active, family)]
    if alone:
        hint = {"same_family": "add another model from the same company for each of them",
                "other_vendor": "add a model from another company"}.get(judges, "")
        raise ConfigError(f"'{judges}' leaves no judge for answers by {', '.join(alone)}" + (f"; {hint}" if hint else ""))
    warnings = []
    if judges == "recuse" and len(active) == 1:
        warnings.append("one model: it judges its own answers, each in a fresh session")
    if judges == "recuse" and len(active) == 2:
        warnings.append("two models: every answer has a single judge")
    return warnings


def judge_context(context: str, *, author_model: str, trace: str) -> str:
    """The block the judge prompt carries between the question and the answer."""
    if context == "isolated":
        return ""
    if context == "author_label":
        return f"Author of this answer: {author_model}\n\n"
    if context == "shared_trace":
        return f"Current population (scores from earlier selections; new answers are not scored yet):\n{trace}\n\n"
    raise ConfigError(f"unknown context {context!r}; expected one of {list(CONTEXT_AXIS)}")
