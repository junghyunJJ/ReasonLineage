"""Command line (spec 8): `reasonlineage run | resume | diagnose | gold`.

This is the one place that wires the engine to the checks package.
"""

import argparse
import asyncio
import json
import os
import random
import signal
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .backends.base import ModelBackend
from .backends.http import HttpBackend
from .checks.base import Checker
from .checks.gate import Gate
from .checks.jev import JevChecker
from .checks.local import LocalLLMChecker
from .diagnose.gold import format_report, score_run, summarize
from .diagnose.j2 import load_gold_items, run_j2
from .diagnose.pmid import efetch, run_pmid_check
from .engine.calls import CallRecorder, ReplaySource, gen0_writing
from .engine.conditions import CONTEXT_AXIS, JUDGE_AXIS, check_conditions
from .engine.config import (
    ConfigError, Member, RunOptions, Setup, Task, build_backend, http_model_lister, load_setup, load_task,
    read_key_file, setup_from_dict, task_from_dict, verify_http_members,
)
from .engine.errors import ResumeMismatch, RunCorrupted, RunStopped
from .engine.events import EventLog
from .engine.header import build_header, cli_versions, engine_commit, experiment_problems, resume_problems
from .engine.policies import FixedPolicies
from .engine.runner import Runner, evolution_config
from .protocol import ProtocolSpec, load_protocol

REPO = Path(__file__).resolve().parents[2]


def build_checker(setup: Setup, task: Task, protocol: ProtocolSpec, env: Mapping[str, str]) -> tuple[Checker | None, str | None]:
    """The checker for this task's data sensitivity, or (None, the reason there is none)."""
    choice = setup.checker_for.get(task.data_sensitivity)
    if choice is None:
        return None, f"no checker is set for {task.data_sensitivity} tasks"
    if choice == "jev":
        key = env.get(setup.jev.api_key_env) or read_key_file(setup.jev.api_key_file)
        if not key:
            where = f"${setup.jev.api_key_env}" + (f" or {setup.jev.api_key_file}" if setup.jev.api_key_file else "")
            return None, f"jev needs an API key in {where}"
        return JevChecker(key, setup.jev.version, data_sensitivity=task.data_sensitivity, base_url=setup.jev.base_url,
                          timeout_s=protocol.timeout("check")), None
    member = setup.local_checkers[choice]
    backend = HttpBackend(member.name, member.base_url, max_concurrency=setup.concurrency, retries=1)
    return LocalLLMChecker(backend, member.model, member.effort, name=member.name,
                           max_tokens=protocol.max_tokens("check"), timeout_s=protocol.timeout("check")), None


def servers(setup: Setup, task: Task) -> list[Member]:
    """The panel, plus the checker when this task's checker is a local model: the servers to probe before any call."""
    choice = setup.checker_for.get(task.data_sensitivity)
    return [*setup.panel, *([setup.local_checkers[choice]] if choice in setup.local_checkers else [])]


@dataclass
class Services:
    """Everything that touches the outside world, so tests can swap it out."""

    backend: Callable[[Member, int], ModelBackend] = build_backend
    list_models: Callable[[Member], list[str]] = http_model_lister
    checker: Callable[..., tuple[Checker | None, str | None]] = build_checker
    versions: Callable[[Sequence[Member]], dict[str, str]] = cli_versions
    pubmed: Callable[[Sequence[str]], str] = efetch
    env: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reasonlineage", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="start a run")
    run.add_argument("task", help="task file (JSON)")
    run.add_argument("--config", default=str(REPO / "configs" / "main.json"), help="setup file with the panel and checkers")
    run.add_argument("--mode", choices=["experiment", "exploration"], default="experiment")
    run.add_argument("--judges", choices=JUDGE_AXIS, default="recuse")
    run.add_argument("--context", choices=CONTEXT_AXIS, default="isolated")
    run.add_argument("--generations", type=int, help="default: protocol.json (3); with --replay, the replayed run's count")
    run.add_argument("--seed", type=int, help="default: a random seed, recorded in header.json")
    reuse = run.add_mutually_exclusive_group()
    reuse.add_argument("--replay", metavar="RUN_DIR", help="reuse every answer recorded by RUN_DIR, with its seed and conditions")
    reuse.add_argument("--gen0-from", metavar="RUN_DIR", help="reuse generation 0 of RUN_DIR")
    run.add_argument("--out", default="runs", help="folder for run folders")
    resume = sub.add_parser("resume", help="continue a stopped or interrupted run")
    resume.add_argument("run_dir")
    diagnose = sub.add_parser("diagnose", help="J2 diagnostics and the PMID check for a finished run")
    diagnose.add_argument("run_dir")
    diagnose.add_argument("--gold-items", help="JSON file: {\"items\": [{\"item\": ..., \"outcome_date\": ...}]}")
    gold = sub.add_parser("gold", help="score finished runs against a gold file (gold design 5.4)")
    gold.add_argument("run_dirs", nargs="+", metavar="RUN_DIR")
    gold.add_argument("--gold", required=True, help="JSON file: {\"tasks\": {task id: {\"approved\": [...], \"failed\": [...]}}}")
    gold.add_argument("--out", help="also write the summary to this JSON file")
    return parser


def _read_header(run_dir: Path) -> dict[str, Any]:
    try:
        return json.loads((run_dir / "header.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"{run_dir} has no readable header.json: {exc}") from None


def gen0_source_problems(source: Path, task: Task, protocol: ProtocolSpec) -> list[str]:
    """Why generation 0 of the run in `source` cannot be shared with a run of this task and protocol."""
    header = _read_header(source)
    problems = []
    if task_from_dict(header["task"]) != task:
        problems.append(f"--gen0-from: {source} ran a different task")
    if header["protocol"]["hash"] != protocol.hash:
        problems.append(f"--gen0-from: {source} used different protocol files (the hash differs)")
    return problems


def _new_run_dir(out: Path, task_id: str) -> Path:
    base = out / f"{datetime.now():%Y%m%d-%H%M%S}-{task_id}"
    run_dir, n = base, 1
    while run_dir.exists():
        n += 1
        run_dir = base.with_name(f"{base.name}-{n}")
    return run_dir


def cmd_run(args: argparse.Namespace, services: Services) -> int:
    protocol = load_protocol()
    task = load_task(args.task)
    setup = load_setup(args.config)
    replay_header = _read_header(Path(args.replay)) if args.replay else None
    if replay_header is not None:
        source = replay_header["options"]
        generations = args.generations if args.generations is not None else source["generations"]
        options = RunOptions(mode=source["mode"], judges=source["judges"], context=source["context"],
                             generations=generations, seed=source["seed"], replay_from=str(args.replay))
        print(f"--replay: using the seed and conditions of {args.replay}, with {generations} generation(s)")
    else:
        options = RunOptions(
            mode=args.mode, judges=args.judges, context=args.context,
            generations=args.generations if args.generations is not None else protocol.generations,
            seed=args.seed if args.seed is not None else random.SystemRandom().randrange(2**31),
            gen0_from=str(args.gen0_from) if args.gen0_from else None,
        )
    checker, why = services.checker(setup, task, protocol, services.env)
    problems = verify_http_members(servers(setup, task), services.list_models)
    if replay_header is not None and task_from_dict(replay_header["task"]) != task:
        problems.append(f"--replay: {args.replay} ran a different task")
    if options.gen0_from:
        problems += gen0_source_problems(Path(options.gen0_from), task, protocol)
    try:
        evolution_config(task, options, protocol, len(setup.panel))
    except ValueError as exc:
        problems.append(f"run options: {exc}")
    if options.mode == "experiment":
        problems += experiment_problems(setup=setup, options=options, protocol=protocol,
                                        checker_available=checker is not None, policies_fixed=True)
    else:
        try:
            check_conditions(options.judges, options.context, [m.name for m in setup.panel],
                             {m.name: m.family_name for m in setup.panel})
        except ConfigError as exc:
            problems.append(str(exc))
    if problems:
        print("Cannot start the run:\n" + "\n".join(f"- {p}" for p in problems), file=sys.stderr)
        return 1
    run_dir = _new_run_dir(Path(args.out), task.id)
    run_dir.mkdir(parents=True)
    header = build_header(run_id=run_dir.name, task=task, setup=setup, options=options, protocol=protocol,
                          versions=services.versions(setup.panel), commit=engine_commit(REPO),
                          checker=checker.name if checker else None, checker_note=why)
    (run_dir / "header.json").write_text(json.dumps(header, ensure_ascii=False, indent=2), encoding="utf-8")
    if checker is None:
        print(f"J1 is skipped for this run: {why}")
    return _execute(run_dir, header, task, setup, options, protocol, checker, services, resume=False, warnings=[])


def cmd_resume(args: argparse.Namespace, services: Services) -> int:
    run_dir = Path(args.run_dir)
    header = _read_header(run_dir)
    protocol = load_protocol()
    task = task_from_dict(header["task"])
    setup = setup_from_dict(header["setup"])
    options = RunOptions(**header["options"])
    http = verify_http_members(servers(setup, task) if header.get("checker") else setup.panel, services.list_models)
    stop, warnings = resume_problems(header, protocol, services.versions(setup.panel), http)
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if stop:
        print("Cannot resume:\n" + "\n".join(f"- {p}" for p in stop), file=sys.stderr)
        return 1
    checker = None
    if header.get("checker"):
        checker, why = services.checker(setup, task, protocol, services.env)
        if checker is None:
            print(f"Cannot resume: the J1 checker cannot be rebuilt ({why})", file=sys.stderr)
            return 1
    return _execute(run_dir, header, task, setup, options, protocol, checker, services, resume=True, warnings=warnings)


STOP_SIGNALS = (signal.SIGTERM, signal.SIGHUP)


async def _cancel_on_signals(coro):
    """Run `coro`, cancelling it on SIGTERM or SIGHUP the way Ctrl-C does.

    The CLIs run in their own sessions (backends/_subprocess.py), so a hangup or SIGTERM no longer reaches them;
    cancelling takes the path that kills each call's process group.
    """
    loop = asyncio.get_running_loop()
    task = asyncio.ensure_future(coro)
    for sig in STOP_SIGNALS:
        loop.add_signal_handler(sig, task.cancel)
    try:
        return await task
    finally:
        for sig in STOP_SIGNALS:
            loop.remove_signal_handler(sig)


def _execute(run_dir: Path, header: Mapping[str, Any], task: Task, setup: Setup, options: RunOptions,
             protocol: ProtocolSpec, checker: Checker | None, services: Services, *, resume: bool,
             warnings: Sequence[str]) -> int:
    events = EventLog(run_dir / "events.jsonl", resume=resume)
    if resume:
        events.note("run.resumed", warnings=list(warnings))
    if options.replay_from:
        replay = ReplaySource(options.replay_from)
    elif options.gen0_from:
        replay = ReplaySource(options.gen0_from, keep=gen0_writing, required=True)
    else:
        replay = None
    recorder = CallRecorder(run_dir, events, options.seed, replay=replay)
    sources = [p for p in (options.replay_from, options.gen0_from) if p]
    gate = Gate(run_dir, checker, protocol, task.question, options.mode, sources=sources) if checker else None
    backends = {m.name: services.backend(m, setup.concurrency) for m in setup.panel}
    runner = Runner(run_dir=run_dir, run_id=header["run_id"], task=task, members=setup.panel, backends=backends,
                    protocol=protocol, options=options, events=events, recorder=recorder, gate=gate, policies=FixedPolicies())
    try:
        summary = asyncio.run(_cancel_on_signals(runner.run()))
    except RunStopped as stop:
        print(f"Run stopped: {stop}\nFix the cause, then run: reasonlineage resume {run_dir}", file=sys.stderr)
        return 2
    except (ResumeMismatch, RunCorrupted) as exc:
        print(f"Cannot continue {run_dir}: {exc}", file=sys.stderr)
        return 1
    except asyncio.CancelledError:
        print(f"Run interrupted by a signal; its CLI calls were stopped. Continue with: reasonlineage resume {run_dir}",
              file=sys.stderr)
        return 143
    print(f"Done: {run_dir} (best {summary['best']['id']} by {summary['best']['author']}, fitness {summary['best']['fitness']:.3f})")
    return 0


def cmd_diagnose(args: argparse.Namespace, services: Services) -> int:
    run_dir = Path(args.run_dir)
    header = _read_header(run_dir)
    protocol = load_protocol()
    task = task_from_dict(header["task"])
    setup = setup_from_dict(header["setup"])
    gold = load_gold_items(args.gold_items) if args.gold_items else []
    checker, why = services.checker(setup, task, protocol, services.env)
    if checker is None:
        print(f"J2 is skipped: {why}")
    else:
        out = asyncio.run(run_j2(run_dir, checker, protocol, task.question, gold))
        print(f"J2: {out}")
    summary = run_pmid_check(run_dir, fetch=services.pubmed)
    print(f"PMIDs: {summary}")
    return 0


LEFT_OUT = {
    "not_a_run": "not a run folder",
    "no_gold": "its task is not in the gold file",
    "mismatch": "its candidates differ from the gold drugs",
    "incomplete": "the run did not finish",
}


def cmd_gold(args: argparse.Namespace, services: Services) -> int:
    try:
        gold = json.loads(Path(args.gold).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"gold file {args.gold}: {exc}") from None
    runs = [score_run(Path(d), gold) for d in args.run_dirs]
    for run in runs:
        if run["status"] in LEFT_OUT:
            print(f"warning: {run['run']}: {LEFT_OUT[run['status']]}; left out", file=sys.stderr)
    report = summarize(runs)
    print(format_report(report))
    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


def main(argv: Sequence[str] | None = None, services: Services | None = None) -> int:
    args = build_parser().parse_args(argv)
    commands = {"run": cmd_run, "resume": cmd_resume, "diagnose": cmd_diagnose, "gold": cmd_gold}
    try:
        return commands[args.command](args, services or Services())
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
