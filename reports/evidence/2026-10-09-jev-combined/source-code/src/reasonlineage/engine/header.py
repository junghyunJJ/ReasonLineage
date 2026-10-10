"""The run header (header.json) and the checks made before a run starts or resumes (spec 6.1, 6.3, 6.6)."""

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..protocol import ProtocolSpec
from .conditions import check_conditions
from .config import ConfigError, Member, RunOptions, Setup, Task

CLI_BINARIES = {"claude": "claude", "codex": "codex", "grok": "grok"}
ALIASES = ("latest", "preview")


def _version_output(argv: list[str]) -> str:
    return subprocess.run(argv, capture_output=True, text=True, timeout=30, check=True).stdout


def cli_versions(members: Sequence[Member], run: Callable[[list[str]], str] = _version_output) -> dict[str, str]:
    """`<cli> --version` for every CLI the panel uses."""
    versions = {}
    for kind in sorted({m.backend for m in members} & set(CLI_BINARIES)):
        try:
            versions[kind] = run([CLI_BINARIES[kind], "--version"]).strip()
        except (OSError, subprocess.SubprocessError) as exc:
            versions[kind] = f"unknown ({exc.__class__.__name__})"
    return versions


def engine_commit(repo: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=10, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def build_header(*, run_id: str, task: Task, setup: Setup, options: RunOptions, protocol: ProtocolSpec,
                 versions: Mapping[str, str], commit: str, checker: str | None, checker_note: str | None) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "protocol": {"version": protocol.version, "hash": protocol.hash},
        "options": options.to_dict(),
        "task": task.to_dict(),
        "setup": setup.to_dict(),
        "checker": checker,
        "checker_note": checker_note,
        "j1_enforce": bool(protocol.j1["enforce"]),
        "cli_versions": dict(versions),
        "engine_commit": commit,
    }


def experiment_problems(*, setup: Setup, options: RunOptions, protocol: ProtocolSpec,
                        checker_available: bool, policies_fixed: bool) -> list[str]:
    """Everything that stops an experiment-mode run from starting (spec 6.6)."""
    problems = []
    if not policies_fixed:
        problems.append("experiment mode needs the fixed policies")
    if options.generations < 0:
        problems.append("experiment mode needs a fixed number of generations (0 or more)")
    for member in setup.panel:
        if any(alias in member.model.lower() for alias in ALIASES):
            problems.append(f"{member.name}: pin a model version instead of the alias {member.model!r}")
    if setup.jev is not None and any(alias in setup.jev.version.lower() for alias in ALIASES):
        problems.append(f"jev: pin a version instead of {setup.jev.version!r}")
    if protocol.j1["enforce"] and not checker_available:
        problems.append("the protocol turns the J1 gate on, but no checker is available for this task")
    try:
        check_conditions(options.judges, options.context, [m.name for m in setup.panel],
                         {m.name: m.family_name for m in setup.panel})
    except ConfigError as exc:
        problems.append(str(exc))
    return problems


def resume_problems(header: Mapping[str, Any], protocol: ProtocolSpec, versions: Mapping[str, str],
                    http_problems: Sequence[str]) -> tuple[list[str], list[str]]:
    """(problems that stop a resume, warnings to record) (spec 6.3)."""
    stop, warn = [], []
    if header["protocol"]["hash"] != protocol.hash:
        stop.append("the protocol files changed since this run started (the hash differs); resume needs the same protocol")
    recorded = header.get("cli_versions", {})
    changed = [f"{kind}: {recorded.get(kind)} -> {now}" for kind, now in versions.items() if recorded.get(kind) != now]
    if changed:
        warn.append("CLI versions changed: " + "; ".join(changed))
    if http_problems:
        (stop if header["options"]["mode"] == "experiment" else warn).extend(http_problems)
    return stop, warn
