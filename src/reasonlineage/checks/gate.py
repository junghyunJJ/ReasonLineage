"""The J1 gate (spec 5.9): check each new answer before judging and tell the engine whether to rewrite it.

Results go to checks.jsonl, never to the engine's event log. They are keyed by the checker,
the question set, and the exact text checked, so a resumed or replayed run reuses them
instead of asking again.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from typing import Any, Mapping, Sequence

from ..engine import answer as fmt
from ..engine.errors import RunStopped
from ..engine.events import read_events
from ..engine.gating import GateDecision
from ..protocol import ProtocolSpec
from .base import Checker, CheckerError, check_key
from .questions import j1_questions
from .combined import verdict as combined_verdict, policy_hash


class Gate:
    def __init__(self, run_dir: str | Path, checker: Checker, protocol: ProtocolSpec, question: str, mode: str,
                 sources: Sequence[str | Path] = ()) -> None:
        self.path = Path(run_dir) / "checks.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.checker = checker
        self.protocol = protocol
        self.question = question
        self.mode = mode
        records = read_events(self.path)
        self._done = {r["key"]: r for r in records}
        self._contexts = {(r['key'], r['candidate'], r['generation'], r['author'], r['attempt']): r for r in records}
        self._sources: dict[str, dict[str, Any]] = {}
        for source in sources:
            for record in read_events(Path(source) / "checks.jsonl"):
                self._sources.setdefault(record["key"], record)

    async def __call__(self, candidate_id: str, generation: int, author: str, answer: Mapping[str, Any],
                       attempt: int) -> GateDecision:
        top = fmt.top_item(answer)
        questions = j1_questions(self.protocol, top)
        state = f"Question:\n{self.question}\n\n{fmt.render_for_judge(answer)}"
        checker_key = self.checker.name
        if self.protocol.j1.get('policy') == 'conditioned':
            checker_key += ':' + policy_hash(self.protocol.j1)
        key = check_key(checker_key, questions, state)
        context = (key, candidate_id, generation, author, attempt)
        record = self._contexts.get(context)
        if record is None:
            base = {"event": "check.j1", "key": key, "candidate": candidate_id, "generation": generation, "author": author,
                    "attempt": attempt, "checker": self.checker.name, "top_item": top}
            source = self._done.get(key) or self._sources.get(key)
            if source is not None:
                found = {k: source.get(k) for k in ("model", "answers", "error", "warning",
                         'initial_answers', 'initial_verdict', 'rechecked', 'recheck')}
                record = {**base, **found, "replayed": True}
            else:
                record = {**base, **(await self._ask(state, questions)), "replayed": False}
            record.update(self._verdict(record))
            if (source is None and not record.get('error') and record.get('needs_review') and
                    self.protocol.j1.get('recheck_attempts', 0) == 1):
                record['initial_answers'] = record['answers']
                record['initial_verdict'] = self._verdict(record)
                recheck_state = ('Proposed answer:\n' + answer['answer'] + '\n\n' +
                                 self.protocol.j1['recheck_instructions'])
                recheck = await self._ask(recheck_state, questions)
                for field in record['initial_verdict']:
                    record.pop(field, None)
                record.update(recheck)
                record['rechecked'] = True
                record['recheck'] = recheck
                record.update(self._verdict(record))
            self._append(record)
            self._done[key] = record
            self._contexts[context] = record
        rewrite = bool(record["would_rewrite"]) and bool(self.protocol.j1["enforce"]) and attempt == 0
        return GateDecision(rewrite, tuple(record["reasons"]))

    async def _ask(self, state: str, questions) -> dict[str, Any]:
        try:
            result = await self.checker.ask(state, questions)
        except (CheckerError, OSError) as exc:
            return {"model": None, "answers": None, "error": str(exc), "warning": None}
        warning = None
        pinned = self.checker.pinned_version
        if pinned is not None and result.model != pinned:
            message = f"{self.checker.name} answered as {result.model}, not the pinned {pinned}"
            if self.mode == "experiment":
                raise RunStopped(message)
            warning = message
        answers = {name: a.to_dict() for name, a in result.answers.items()}
        return {"model": result.model, "answers": answers, "error": None, "warning": warning}

    def _verdict(self, record: Mapping[str, Any]) -> dict[str, Any]:
        """Would this answer be rewritten? Uses the thresholds in protocol.json."""
        j1 = self.protocol.j1
        answers = record.get("answers")
        if j1.get('policy') == 'conditioned':
            return combined_verdict(answers, j1)
        if not answers:
            return {"would_rewrite": False, "reasons": [], "enforced": bool(j1["enforce"])}
        reasons = []
        normal = answers["answer_type"]["probabilities"].get(j1["questions"]["answer_type"]["pass"], 0.0)
        if normal < j1["thresholds"]["answer_type"]:
            reasons.append(j1["rewrite_reasons"]["answer_type"])
        if answers["top_item_argument"]["probabilities"].get("yes", 0.0) < j1["thresholds"]["top_item_argument"]:
            reasons.append(Template(j1["rewrite_reasons"]["top_item_argument"]).substitute(top_item=record["top_item"]))
        return {"would_rewrite": bool(reasons), "reasons": reasons, "enforced": bool(j1["enforce"])}

    def _append(self, record: Mapping[str, Any]) -> None:
        stamped = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **record}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(stamped, ensure_ascii=False) + "\n")
