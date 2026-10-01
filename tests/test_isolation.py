"""The engine never sees checker results except the rewrite decision (spec 3.4, test 4)."""

import ast
import asyncio
from pathlib import Path

import pytest

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


GOLD_MODULES = ("reasonlineage.gold", "reasonlineage.diagnose.gold")


def imports_gold(path: Path) -> bool:
    """Does the file import the gold tools, absolutely or relatively (gold design 2, criterion 2)?"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name.startswith(GOLD_MODULES) for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom):
            module, names = node.module or "", {a.name for a in node.names}
            if module.startswith(GOLD_MODULES) or (module == "reasonlineage.diagnose" and "gold" in names):
                return True
            if node.level and (module.split(".")[0] == "gold" or module == "diagnose.gold" or (module == "diagnose" and "gold" in names)):
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


def test_core_engine_and_checks_never_import_the_gold_tools():
    offenders = [p for folder in ("core", "engine", "checks") for p in (SRC / folder).glob("*.py") if imports_gold(p)]
    assert offenders == []


@pytest.mark.parametrize("line", [
    "from ..gold import build\n", "from ..diagnose.gold import score_run\n", "from ..diagnose import gold\n",
    "import reasonlineage.gold.repodb\n", "from reasonlineage.diagnose import gold\n",
])
def test_the_gold_import_check_catches_real_imports(tmp_path, line):
    bad = tmp_path / "bad.py"
    bad.write_text(line)
    assert imports_gold(bad)
