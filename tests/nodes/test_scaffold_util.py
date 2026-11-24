from dataclasses import dataclass, field
from pathlib import Path

from fakes import ROOT, FakeFs

from ambler.nodes.scaffold_util import Outcome, ScaffoldUtil

UTIL_FILE = ROOT / "src" / "demo" / "utils" / "terminal.py"


@dataclass
class MockState:
    argv: list[str] = field(default_factory=list[str])
    exit_code: int = 0


async def test_writes_the_util_module() -> None:
    fs = FakeFs()
    state = MockState(argv=["Terminal"])
    assert await ScaffoldUtil(fs).run(state) == Outcome.DONE
    assert "class TerminalUtils(Protocol)" in fs.files[UTIL_FILE]
    assert "class SystemTerminalUtils" in fs.files[UTIL_FILE]
    assert fs.out == [f"Created {UTIL_FILE}"]
    assert state.exit_code == 0


async def test_existing_util_fails_with_exit_code_1() -> None:
    fs = FakeFs({UTIL_FILE: "old"})
    state = MockState(argv=["terminal"])
    assert await ScaffoldUtil(fs).run(state) == Outcome.FAILED
    assert fs.files[UTIL_FILE] == "old"
    assert state.exit_code == 1
    assert "already exists" in fs.errors[0]


async def test_missing_name_fails_with_exit_code_2() -> None:
    fs = FakeFs()
    state = MockState()
    assert await ScaffoldUtil(fs).run(state) == Outcome.FAILED
    assert state.exit_code == 2
    assert fs.files == {}


async def test_no_project_fails_with_exit_code_1() -> None:
    fs = FakeFs(package=None)
    state = MockState(argv=["terminal"])
    assert await ScaffoldUtil(fs).run(state) == Outcome.FAILED
    assert state.exit_code == 1
    assert fs.errors == ["Error: No pyproject.toml found in current folder."]
    assert fs.files == dict[Path, str]()
