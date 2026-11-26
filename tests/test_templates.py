"""What the scaffolders write passes a generated project's own checks.

``ambler check`` runs ``ruff format --check``, ``ruff check`` and ``pyright`` before
the tests, so nodes, their tests, walks and their wiring tests must pass all three
as written: unfinished, but formatted, lint-clean and well typed.
"""

import inspect
import subprocess
import sys
from pathlib import Path

import pytest

import ambler
from ambler.nodes.scaffold_node import Outcome as NodeOutcome
from ambler.nodes.scaffold_node import ScaffoldNode
from ambler.nodes.scaffold_walk import Outcome, ScaffoldWalk
from ambler.utils.fs import SystemScaffoldUtils
from ambler.utils.templates import (
    StateField,
    render_node,
    render_node_test,
    render_protocols,
    render_util,
)

PKG = "demo_app"

PYPROJECT = """[project]
name = "demo-app"
version = "0.1.0"
requires-python = ">=3.12"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]

[tool.pyright]
include = ["src", "tests"]
extraPaths = ["src"]
typeCheckingMode = "strict"
reportMatchNotExhaustive = true
"""

INIT = '"""Node package."""\n\nfrom pathlib import Path\nfrom typing import Protocol\n'

NODES: dict[str, dict[str, object]] = {
    "greet": {
        "terminal": False,
        "fallible": True,
        "outcomes": ["DONE"],
        "state_fields": [("name", "str")],
    },
    "bye": {
        "terminal": True,
        "fallible": False,
        "outcomes": [],
        "state_fields": [("name", "str")],
    },
    "count": {
        "terminal": False,
        "fallible": False,
        "outcomes": ["AGAIN", "FINISHED"],
        "state_fields": [("count", "int"), ("log", "list[str]"), ("path", "Path")],
    },
    "tick": {
        "terminal": True,
        "fallible": True,
        "outcomes": [],
        "state_fields": [],
    },
}

UTILS = '''class Utils(Protocol):
    """The side effects this node needs: one method each, faked in the tests."""'''

SLEEP = (
    UTILS
    + "\n\n    async def sleep(self, duration: timedelta) -> None: ...\n\n"
    + '    def heads(self) -> bool:\n        """Flips a coin."""\n        ...'
)


SYSTEM = '''class SystemUtils:
    """The real side effects."""'''

MOCK = '''class MockUtils:
    """Fakes every side effect of the node."""'''

IMPLEMENTED = (
    "\n\n    async def sleep(self, duration: timedelta) -> None:\n        pass\n\n"
    "    def heads(self) -> bool:\n        return True"
)


def _node(name: str, spec: dict[str, object]) -> str:
    source = render_node(PKG, name.capitalize(), **spec)  # type: ignore[arg-type]
    if name == "count":
        source = (
            source.replace(
                "from dataclasses import dataclass, field\n",
                "from dataclasses import dataclass, field\n"
                "from datetime import timedelta\n",
            )
            .replace(UTILS, SLEEP)
            .replace(SYSTEM, SYSTEM + IMPLEMENTED)
        )
    return source


def _node_test(name: str, spec: dict[str, object]) -> str:
    source = render_node_test(PKG, name, name.capitalize(), **spec)  # type: ignore[arg-type]
    if name == "count":
        # A type the node scaffold cannot import for you; the developer adds it.
        source = source.replace(
            "from dataclasses import dataclass, field\n",
            "from dataclasses import dataclass, field\nfrom datetime import timedelta\n"
            "from pathlib import Path\n",
        ).replace(MOCK, MOCK + IMPLEMENTED)
    return source


def _project(root: Path) -> None:
    """A generated project with a node from every variant of the node template."""
    (root / "pyproject.toml").write_text(PYPROJECT)
    src = root / "src" / PKG
    tests = root / "tests"
    for folder in (src / "nodes", src / "walks", src / "utils", tests / "nodes"):
        folder.mkdir(parents=True)
    (src / "__init__.py").write_text('"""Demo."""\n')
    (src / "engine.py").write_text(inspect.getsource(ambler))
    fields: list[StateField] = [
        field
        for spec in NODES.values()
        for field in spec["state_fields"]  # type: ignore[union-attr]
    ]
    (src / "nodes" / "__init__.py").write_text(render_protocols(INIT, fields))
    for name, spec in NODES.items():
        (src / "nodes" / f"{name}.py").write_text(_node(name, spec))
        (tests / "nodes" / f"test_{name}.py").write_text(_node_test(name, spec))
    (src / "utils" / "journal.py").write_text(render_util("journal", "Journal"))
    (src / "board.py").write_text(
        '"""A type the nodes import by path."""\n\n\nclass Board:\n    """A board."""\n'
    )


PLACE = [
    "place",
    "--terminal",
    "--state",
    f"board:{PKG}.board.Board",
    "--state",
    f"boards:list[{PKG}.board.Board]",
    "--state",
    "stamp:datetime.datetime | None",
    "--state",
    "path",
]
"""A node scaffolded through ``ScaffoldNode``, with types given by their paths."""


def _run(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", *args],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The project, with a walk wired completely and one left unwired."""
    root = tmp_path_factory.mktemp("project")
    _project(root)
    walks = [
        ["hello", "--nodes", "greet,bye", "--edge", "greet.done=bye"],
        ["loop", "--nodes", "count,tick", "--edge", "count.again=count"],
    ]

    async def scaffold() -> None:
        class Here(SystemScaffoldUtils):
            def root(self) -> Path:
                return root

        state = _State(PLACE)
        assert await ScaffoldNode(Here()).run(state) == NodeOutcome.DONE
        for argv in walks:
            state = _State(argv)
            assert await ScaffoldWalk(Here()).run(state) == Outcome.DONE

    import asyncio

    asyncio.run(scaffold())
    return root


class _State:
    def __init__(self, argv: list[str]) -> None:
        self.argv = argv
        self.exit_code = 0


@pytest.mark.parametrize(
    "args",
    [
        ("ruff", "format", "--check", "--diff", "."),
        ("ruff", "check", "."),
        ("pyright",),
    ],
    ids=["format", "lint", "types"],
)
def test_scaffolded_files_pass_the_projects_checks(
    project: Path, args: tuple[str, ...]
) -> None:
    result = _run(project, *args)
    assert result.returncode == 0, result.stdout + result.stderr


def test_types_given_by_path_are_imported_into_the_nodes_package(
    project: Path,
) -> None:
    init = (project / "src" / PKG / "nodes" / "__init__.py").read_text()
    assert "from datetime import datetime\n" in init
    assert f"from {PKG}.board import Board\n" in init
    assert "    board: Board\n" in init
    assert "    boards: list[Board]\n" in init
    assert "    stamp: datetime | None\n" in init
    test = (project / "tests" / "nodes" / "test_place.py").read_text()
    assert "    board: Board = field(default_factory=Board)\n" in test
    assert "    stamp: datetime | None = None\n" in test


def test_the_walks_get_scripts(project: Path) -> None:
    pyproject = (project / "pyproject.toml").read_text()
    assert 'hello = "demo_app.walks.hello:main"' in pyproject
    assert 'loop = "demo_app.walks.loop:main"' in pyproject
