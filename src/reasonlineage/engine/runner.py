"""One evolution run (spec 5.3): write, check, judge, select, repeat.

Every model call goes through the CallRecorder, and every decision goes to the event log in
a fixed order, so running the same recorded calls again reproduces the same run.
"""

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Iterable, Mapping, Sequence

from ..backends.base import BackendError, ModelBackend, ModelRequest
from ..core.models import Candidate, JudgeScore
from ..core.state import EvolutionConfig, EvolutionState, seeds_per_model
from ..prompts import score_schema
from ..protocol import ProtocolSpec
from . import answer as fmt
from .calls import CallRecorder
from .conditions import check_conditions, judge_context, judge_set
from .config import Member, RunOptions, Task
from .errors import RunStopped
from .events import EventLog
from .gating import J1Gate
from .policies import FixedPolicies, Policies


class WritingFailed(Exception):
    """An author call produced no usable answer."""


@dataclass
class Written:
    author: str
    data: dict[str, Any]
    versions: list[str]
    anomalies: list[dict[str, Any]] = field(default_factory=list)


async def gather_all(coros: Iterable[Awaitable]) -> list:
    """Like asyncio.gather, but cancels the other calls as soon as one raises."""
    tasks = [asyncio.ensure_future(c) for c in coros]
    try:
        return await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


def parse_judge(judge: str, data: Any, dims: Sequence[str]) -> JudgeScore:
    """A judge's structured output as a JudgeScore; ValueError when it is unusable."""
    if not isinstance(data, Mapping):
        raise ValueError("judge output is not an object")
    scores = {}
    for dim in dims:
        value = data.get(dim)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ValueError(f"judge output has no valid score for {dim}: {value!r}")
        scores[dim] = float(value)
    critique = data.get("critique")
    if not isinstance(critique, list) or not 1 <= len(critique) <= 3 or not all(isinstance(c, str) for c in critique):
        raise ValueError("judge output needs 1-3 critique strings")
    return JudgeScore(judge, scores, tuple(critique))


class Runner:
    def __init__(self, *, run_dir: str | Path, run_id: str, task: Task, members: Sequence[Member],
                 backends: Mapping[str, ModelBackend], protocol: ProtocolSpec, options: RunOptions,
                 events: EventLog, recorder: CallRecorder, gate: J1Gate | None = None,
                 policies: Policies | None = None) -> None:
        self.run_dir = Path(run_dir)
        self.run_id = run_id
        self.task = task
        self.members = {m.name: m for m in members}
        self.names = [m.name for m in members]
        self.family = {m.name: m.family_name for m in members}
        self.backends = backends
        self.protocol = protocol
        self.options = options
        self.events = events
        self.recorder = recorder
        self.gate = gate
        self.policies = policies or FixedPolicies()
        self.dims = list(task.weights)
        self.answers: dict[str, dict[str, Any]] = {}
        self._next_id = 0
        self._synthesizers: list[str] = []

    # --- setup ---

    def evolution_config(self) -> EvolutionConfig:
        experiment = self.options.mode == "experiment"
        margins = self.protocol.margins
        return EvolutionConfig.for_roster(
            len(self.names), self.task.weights,
            threshold=self.task.threshold,
            generation_limit=self.options.generations,
            early_stop=not experiment,
            stagnation_recovery=not experiment,
            tie_margin=margins["tie"],
            dominance_margin=margins["dominance"],
            stagnation_threshold=margins["stagnation"],
            stagnation_window=margins["stagnation_window"],
        )

    def _new_id(self) -> str:
        self._next_id += 1
        return f"c{self._next_id:03d}"

    # --- the run ---

    async def run(self) -> dict[str, Any]:
        self.events.emit("run.started", run_id=self.run_id, protocol_hash=self.protocol.hash, **self.options.to_dict())
        for warning in check_conditions(self.options.judges, self.options.context, self.names, self.family):
            self.events.emit("anomaly", kind="reliability", candidate=None, detail=warning, action="proceed")
        try:
            state = await self._generation_zero()
            await self._score(state)
            while not state.is_done:
                result = state.select()
                if result is None:
                    break
                self.events.emit(
                    "selection", generation=state.generation - 1,
                    survivors=[c.id for c in result.survivors], eliminated=[c.id for c in result.eliminated],
                    excluded=[c.id for c in result.excluded],
                    tie_break_swap=list(result.tie_break_swap) if result.tie_break_swap else None,
                )
                await self._offspring(state)
                await self._score(state)
        except RunStopped as stop:
            self.events.stop(str(stop))
            raise
        best = state.best
        self.events.emit("run.completed", termination=str(state.termination), best=best.id, generation=state.generation)
        self.events.finish()
        summary = {
            "run_id": self.run_id,
            "task": self.task.id,
            "termination": str(state.termination),
            "generations": state.generation,
            "best": {"id": best.id, "author": best.author, "fitness": best.fitness, "scores": best.scores,
                     "answer": self.answers[best.id]},
            "population": [{"id": c.id, "author": c.author, "fitness": c.fitness} for c in state.population],
        }
        (self.run_dir / "result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary

    async def _generation_zero(self) -> EvolutionState:
        per_model = seeds_per_model(len(self.names))
        approaches = self.protocol.approaches
        jobs = []
        for name in self.names:
            for j in range(per_model):
                approach = approaches[j % len(approaches)] if per_model > 1 else None
                jobs.append((self._new_id(), name, approach))
        written = await gather_all(
            self._write_or_substitute(0, "write", cid, name, self._seed_prompt(approach)) for cid, name, approach in jobs
        )
        seeds = [self._record_candidate(cid, w, "seed", (), 0) for (cid, _, _), w in zip(jobs, written)]
        return EvolutionState(self.evolution_config(), seeds)

    async def _offspring(self, state: EvolutionState) -> None:
        gen = state.generation
        survivors = list(state.population)
        parent = self.policies.mutation_parent(survivors)
        plan = self.policies.crossover_plan(survivors, self.names, self._synthesizers)
        jobs = [  # (candidate id, role, operator, author, prompt, parent ids, authors to avoid)
            (self._new_id(), "mutate", "mutation", parent.author, self._mutate_prompt(parent), (parent.id,), ()),
        ]
        cross_id = self._new_id()
        jobs.append((cross_id, "cross", "crossover", plan.synthesizer, self._crossover_prompt(plan.parents),
                     tuple(p.id for p in plan.parents), tuple(p.author for p in plan.parents)))
        written = await gather_all(
            self._write_or_substitute(gen, role, cid, author, prompt, avoid)
            for cid, role, _, author, prompt, _, avoid in jobs
        )
        if plan.fallback:
            self.events.emit("anomaly", kind="synthesizer_fallback", candidate=cross_id,
                             detail=f"every model wrote a parent; {plan.synthesizer} synthesizes", action="proceed")
        for (cid, _, operator, _, _, parents, _), w in zip(jobs, written):
            if operator == "crossover":
                self._synthesizers.append(w.author)
            state.register(self._record_candidate(cid, w, operator, parents, gen))
        state.start_scoring()

    def _record_candidate(self, cid: str, w: Written, operator: str, parents: Sequence[str], generation: int) -> Candidate:
        for anomaly in w.anomalies:
            self.events.emit("anomaly", **anomaly)
        self.answers[cid] = w.data
        self.events.emit("candidate.created", id=cid, author=w.author, operator=operator, parents=list(parents),
                         generation=generation, versions=w.versions, answer=w.data)
        return Candidate(cid, fmt.to_content(w.data), w.author, operator, tuple(parents), generation)

    # --- writing ---

    async def _write_or_substitute(self, gen: int, role: str, cid: str, author: str, prompt: str,
                                   avoid: Sequence[str] = ()) -> Written:
        try:
            return await self._write(gen, role, cid, author, prompt)
        except (BackendError, WritingFailed) as exc:
            raise RunStopped(f"{role} {cid} by {author} failed: {exc}") from exc

    async def _write(self, gen: int, role: str, cid: str, author: str, prompt: str) -> Written:
        name = f"g{gen}/{role}/{cid}/{author}"
        data = await self._author_call(name, author, prompt)
        issues = fmt.validate_answer(data, self.task.candidates)
        if issues.hard:
            raise WritingFailed(" ".join(issues.hard))
        anomalies = []
        if issues.soft:
            anomalies.append({"kind": "prose_mention", "candidate": cid, "detail": list(issues.soft), "action": "proceed"})
        return Written(author, data, [name], anomalies)

    def _author_request(self, author: str, prompt: str) -> ModelRequest:
        member = self.members[author]
        low, high = self.protocol.answer_words
        if self.task.candidates:
            rule = "Rank exactly these items, each once, using these exact names: " + ", ".join(self.task.candidates) + "."
        else:
            few, many = self.protocol.open_items
            rule = f"Choose the items to rank yourself: between {few} and {many} items."
        return ModelRequest(
            system=self.protocol.render("author_system", length_min=low, length_max=high, item_rule=rule),
            prompt=prompt, model=member.model, effort=member.effort,
            json_schema=fmt.answer_schema(self.task.candidates, self.protocol.open_items),
            timeout_s=self.protocol.timeout("write"), max_tokens=self.protocol.max_tokens("write"),
        )

    async def _author_call(self, name: str, author: str, prompt: str) -> dict[str, Any]:
        response = await self.recorder.call(name, author, self.backends[author], self._author_request(author, prompt))
        try:
            return fmt.normalize_answer(response.data, self.task.candidates)
        except ValueError as exc:
            raise WritingFailed(str(exc)) from exc

    def _seed_prompt(self, approach: str | None) -> str:
        line = f"Take this approach: {approach}. " if approach else ""
        return self.protocol.render("seed", question=self.task.question, approach_line=line)

    def _critique_lines(self, candidate: Candidate) -> str:
        return "\n".join(f"- {point}" for point in candidate.critique) or "- (no critique points)"

    def _mutate_prompt(self, parent: Candidate) -> str:
        return self.protocol.render("mutate", question=self.task.question,
                                    answer=fmt.render_for_judge(self.answers[parent.id]), critique=self._critique_lines(parent))

    def _crossover_prompt(self, parents: Sequence[Candidate]) -> str:
        blocks = [
            f"Parent {i}:\n{fmt.render_for_judge(self.answers[p.id])}\n\nCritique of parent {i}:\n{self._critique_lines(p)}"
            for i, p in enumerate(parents, 1)
        ]
        return self.protocol.render("crossover", question=self.task.question, parents="\n\n".join(blocks))

    # --- judging ---

    def _trace(self, state: EvolutionState) -> str:
        lines = [f"- {c.id}: fitness {c.fitness:.2f}; ranking: {fmt.ranking_line(self.answers[c.id])}" for c in state.population]
        lines += [f"- {c.id}: not scored yet; ranking: {fmt.ranking_line(self.answers[c.id])}" for c in state.pending]
        return "\n".join(lines)

    async def _score(self, state: EvolutionState) -> None:
        pending = list(state.pending)
        trace = self._trace(state) if self.options.context == "shared_trace" else ""
        jobs = [(c, judge) for c in pending for judge in judge_set(self.options.judges, c.author, self.names, self.family)]
        outcomes = await gather_all(self._judge(state.generation, c, judge, trace) for c, judge in jobs)
        panels: dict[str, list[JudgeScore]] = {c.id: [] for c in pending}
        for (candidate, judge), outcome in zip(jobs, outcomes):
            panels[candidate.id].append(outcome)
            self.events.emit("judge.scored", candidate=candidate.id, judge=judge, author=candidate.author,
                             generation=state.generation, judges_axis=self.options.judges, context=self.options.context,
                             scores=dict(outcome.scores), critique=list(outcome.critique))
        for candidate in pending:
            scored = state.record_score(candidate.id, panels[candidate.id])
            self.events.emit("candidate.scored", candidate=candidate.id, judges=[s.judge for s in panels[candidate.id]],
                             scores=scored.scores, fitness=scored.fitness)

    async def _judge(self, gen: int, candidate: Candidate, judge: str, trace: str) -> JudgeScore:
        member = self.members[judge]
        context = judge_context(self.options.context, author_model=self.members[candidate.author].model, trace=trace)
        request = ModelRequest(
            system=self.protocol.render("judge_system", emphasis=self.task.emphasis, dimensions=", ".join(self.dims)),
            prompt=self.protocol.render("judge_candidate", question=self.task.question, context=context,
                                        candidate=fmt.render_for_judge(self.answers[candidate.id])),
            model=member.model, effort=member.effort, json_schema=score_schema(self.dims),
            timeout_s=self.protocol.timeout("judge"), max_tokens=self.protocol.max_tokens("judge"),
        )
        try:
            response = await self.recorder.call(f"g{gen}/judge/{candidate.id}/{judge}", judge, self.backends[judge], request)
            return parse_judge(judge, response.data, self.dims)
        except (BackendError, ValueError) as exc:
            raise RunStopped(f"judge {judge} on {candidate.id} failed: {exc}") from exc
