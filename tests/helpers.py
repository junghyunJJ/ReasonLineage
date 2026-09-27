from reasonlineage.core import Candidate, JudgeScore

WEIGHTS = {"evidenceCoverage": 0.30, "specificity": 0.30, "novelty": 0.20, "actionability": 0.20}


def uniform(value: float, judge: str = "j") -> JudgeScore:
    """A judge that gives the same score on every dimension, so fitness == value."""
    return JudgeScore(judge=judge, scores={dim: value for dim in WEIGHTS}, critique=(f"{judge}: fix {value}",))


def scored(cid: str, fitness: float, author: str = "a", operator: str = "seed", parents: tuple = ()) -> Candidate:
    return Candidate(id=cid, content=cid, author=author, operator=operator, parent_ids=parents, fitness=fitness)

