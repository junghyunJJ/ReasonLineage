"""Task files and the gold file from the curation record (gold design 4.5, 4.6).

The task files use the engine's task format. The gold file is separate and only the analysis
tools read it, so the engine never sees which drug is the approved one.
"""

import hashlib
import json
import random
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import repodb

QUESTION = ("Which of these drugs is most promising for treating {name}? Rank the candidates, "
            "and give the mechanism, the key evidence, and a validation experiment for the top pick.")


class CurationError(ValueError):
    """The curation record breaks a rule of gold design 4.5, or the task folder holds files it does not build."""


def task_id(display_name: str) -> str:
    return "repodb-" + re.sub(r"[^a-z0-9]+", "-", display_name.lower()).strip("-")


def shuffled(items: Sequence[str], key: str) -> list[str]:
    """The items in an order fixed by `key`, so the approved drug is not always in the same place."""
    order = list(items)
    random.Random(int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)).shuffle(order)
    return order


def check_curation(curation: Mapping[str, Any], pool: Sequence[Mapping[str, Any]]) -> list[str]:
    """What breaks the rules in the curation record, checked against the candidate pool; empty when usable."""
    by_ind = {c["ind_id"]: c for c in pool}
    problems: list[str] = []
    seen: set[str] = set()
    ids: set[str] = set()
    for task in curation["tasks"]:
        where = task.get("id") or task.get("ind_id")
        candidate = by_ind.get(task["ind_id"])
        if candidate is None:
            problems.append(f"{where}: {task['ind_id']} is not in the candidate pool")
            continue
        if task["ind_id"] in seen:
            problems.append(f"{where}: a second task for {task['ind_id']}; one task per indication")
        seen.add(task["ind_id"])
        if task["id"] != task_id(task["display_name"]):
            problems.append(f"{where}: the id must be {task_id(task['display_name'])}")
        if task["id"] in ids:
            problems.append(f"{where}: another task has the same id; give one of them another display name")
        ids.add(task["id"])
        failed = [f["drug"] for f in task["failed"]]
        if len(failed) != 2 or len({task["approved"]["drug"], *failed}) != 3:
            problems.append(f"{where}: a task needs one approved and two different failed drugs")
        if task["approved"]["drug"] not in candidate["approved"]:
            problems.append(f"{where}: {task['approved']['drug']} is not approved for {candidate['indication']} in repoDB")
        for entry in task["failed"]:
            known = {f["nct"] for f in candidate["failed"] if f["drug"] == entry["drug"]}
            if not known:
                problems.append(f"{where}: {entry['drug']} has no efficacy or safety failure for {candidate['indication']} in repoDB")
            elif not entry["ncts"] or not set(entry["ncts"]) <= known:
                problems.append(f"{where}: {entry['drug']}'s trials must be among {sorted(known)}")
        for part in (task["approved"], *task["failed"]):
            if not part.get("why"):
                problems.append(f"{where}: {part['drug']} needs a reason ('why')")
    return problems


def build(curation: Mapping[str, Any], pool: Sequence[Mapping[str, Any]], tasks_dir: str | Path,
          gold_path: str | Path) -> list[Path]:
    """Write one task file per curated task and the gold file; nothing is written if the curation breaks a rule.

    The task folder must hold only the files this curation builds: the run script runs every file in it.
    """
    problems = check_curation(curation, pool)
    tasks_dir, gold_path = Path(tasks_dir), Path(gold_path)
    built = {f"{task['id']}.json" for task in curation["tasks"]}
    problems += [f"{path} is not built by this curation; delete it, then build again"
                 for path in sorted(tasks_dir.glob("*.json")) if path.name not in built]
    if problems:
        raise CurationError("; ".join(problems))
    tasks_dir.mkdir(parents=True, exist_ok=True)
    gold = {"source": {"repo": "zietzm/repoDB", "commit": repodb.COMMIT, "path": "data/repoDB.csv", "sha256": repodb.SHA256},
            "tasks": {}}
    written = []
    for task in curation["tasks"]:
        failed = [f["drug"] for f in task["failed"]]
        body = {"id": task["id"], "question": QUESTION.format(name=task["display_name"]),
                "candidates": shuffled([task["approved"]["drug"], *failed], task["id"]),
                "category": "biomedical", "data_sensitivity": "public"}
        path = tasks_dir / f"{task['id']}.json"
        path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)
        gold["tasks"][task["id"]] = {"approved": [task["approved"]["drug"]], "failed": failed}
    gold_path.parent.mkdir(parents=True, exist_ok=True)
    gold_path.write_text(json.dumps(gold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return written
