"""The scaffolded files pass a generated project's own ``ruff`` checks as written.

``ambler check`` runs ``ruff format --check`` and ``ruff check`` before anything
else, so code the CLI writes must already be formatted and lint-clean.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from ambler.utils.templates import (
    PACKAGE_INIT,
    StateField,
    render_node,
    render_node_test,
    render_protocols,
    render_util,
    render_walk,
    render_walk_test,
)

PKG = "demo_app"

PYPROJECT = """[project]
name = "demo-app"
version = "0.1.0"
requires-python = ">=3.12"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]
"""

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
        "state_fields": [("count", "int"), ("done", "bool")],
    },
    "tick": {
        "terminal": True,
        "fallible": True,
        "outcomes": [],
        "state_fields": [],
    },
}


def _project(tmp_path: Path) -> Path:
    """A generated project holding one file from every template."""
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    src = tmp_path / "src" / PKG
    tests = tmp_path / "tests"
    for folder in (
        src / "nodes",
        src / "walks",
        src / "utils",
        tests / "nodes",
        tests / "walks",
    ):
        folder.mkdir(parents=True)
    (src / "__init__.py").write_text('"""Demo."""\n')
    fields: list[StateField] = [
        field
        for spec in NODES.values()
        for field in spec["state_fields"]  # type: ignore[union-attr]
    ]
    (src / "nodes" / "__init__.py").write_text(render_protocols(PACKAGE_INIT, fields))
    for name, spec in NODES.items():
        cls_name = name.capitalize()
        (src / "nodes" / f"{name}.py").write_text(
            render_node(PKG, cls_name, **spec)  # type: ignore[arg-type]
        )
        (tests / "nodes" / f"test_{name}.py").write_text(
            render_node_test(PKG, name, cls_name, **spec)  # type: ignore[arg-type]
        )
    (src / "walks" / "hello.py").write_text(
        render_walk(PKG, "hello", "Hello", ["greet", "bye"], [("greet", "DONE", "bye")])
    )
    (src / "walks" / "loop.py").write_text(
        render_walk(PKG, "loop", "Loop", ["count", "tick"], [])
    )
    (tests / "walks" / "test_hello.py").write_text(
        render_walk_test(PKG, "hello", "Hello", "greet")
    )
    (src / "utils" / "journal.py").write_text(render_util("journal", "Journal"))
    return tmp_path


def _ruff(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ruff", *args],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "args",
    [("format", "--check", "--diff", "."), ("check", ".")],
    ids=["format", "lint"],
)
def test_scaffolded_files_pass_the_projects_ruff_checks(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    result = _ruff(_project(tmp_path), *args)
    assert result.returncode == 0, result.stdout + result.stderr
