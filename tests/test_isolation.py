"""The engine never sees checker results except the rewrite decision (spec 3.4, test 4)."""

import ast
import asyncio
from pathlib import Path

from fakes import FakeChecker, decisions, make_runner
from reasonlineage.checks.gate import Gate
from reasonlineage.protocol import load_protocol

SRC = Path(__file__).resolve().parents[1] / "src" / "reasonlineage"


def imports_checks(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name.startswith("reasonlineage.checks") for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("reasonlineage.checks") or (node.level and module.split(".")[0] == "checks"):
                return True
    return False


def test_core_and_engine_do_not_import_checks():
    offenders = [p for folder in ("core", "engine") for p in (SRC / folder).glob("*.py") if imports_checks(p)]
    assert offenders == []


def test_the_import_check_catches_a_real_import(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("from ..checks import gate\n")
    assert imports_checks(bad)


def test_with_the_gate_off_checker_results_change_nothing(tmp_path):
    protocol = load_protocol()
    outcomes = []
    for name, checker in [("a", FakeChecker(normal=0.95, argued=0.95)), ("b", FakeChecker(normal=0.05, argued=0.05))]:
        gate = Gate(tmp_path / name, checker, protocol, "Q", "experiment")
        runner, _ = make_runner(tmp_path, run_name=name, gate=gate, generations=2)
        asyncio.run(runner.run())
        outcomes.append([d for d in decisions(tmp_path / name) if d["event"] != "run.started"])
    assert outcomes[0] == outcomes[1]
    assert (tmp_path / "a" / "checks.jsonl").read_text() != (tmp_path / "b" / "checks.jsonl").read_text()
