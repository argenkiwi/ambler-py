from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Protocol

from ambler.nodes import HasArgv, HasExitCode
from ambler.utils.args import ArgParser, UsageError
from ambler.utils.fs import ProjectError
from ambler.utils.fs import ScaffoldUtils as Utils
from ambler.utils.fs import SystemScaffoldUtils as SystemUtils
from ambler.utils.naming import to_pascal, to_shout, to_snake
from ambler.utils.templates import (
    Edge,
    render_walk,
    render_walk_spec,
    render_walk_test,
)


class Outcome(Enum):
    """Whether the walk was written."""

    DONE = auto()
    FAILED = auto()


class State(HasArgv, HasExitCode, Protocol):
    pass


@dataclass(frozen=True)
class ScaffoldWalk:
    """Writes ``src/<pkg>/walks/<name>.py``, its test, and ``specs/<name>.md`` when
    that does not exist yet."""

    utils: Utils = field(default_factory=SystemUtils)

    async def run(self, state: State) -> Outcome:
        parser = ArgParser()
        parser.add_argument("name")
        parser.add_argument("--nodes", required=True)
        parser.add_argument("--edge", action="append")
        parser.add_argument("--no-runner", action="store_true")
        try:
            args = parser.parse_args(state.argv)
        except UsageError as e:
            return self._fail(state, 2, f"Error: {e}")

        node_names = [to_snake(n.strip()) for n in args.nodes.split(",") if n.strip()]
        if not node_names:
            return self._fail(
                state, 2, "Error: --nodes must contain at least one node name"
            )

        try:
            pkg = self.utils.package_name()
        except ProjectError as e:
            return self._fail(state, 1, f"Error: {e}")

        name = to_snake(args.name)
        cls_name = to_pascal(name)
        root = self.utils.root()
        walks_dir = root / "src" / pkg / "walks"
        tests_dir = root / "tests" / "walks"
        specs_dir = root / "specs"
        walk_file = walks_dir / f"{name}.py"
        test_file = tests_dir / f"test_{name}.py"
        spec_file = specs_dir / f"{name}.md"

        if self.utils.exists(walk_file):
            return self._fail(
                state, 1, f"Error: Walk {name} already exists at {walk_file}"
            )

        for directory in (walks_dir, tests_dir, specs_dir):
            self.utils.mkdir(directory)

        self.utils.write_text(
            walk_file,
            render_walk(pkg, name, cls_name, node_names, _parse_edges(args.edge or [])),
        )
        if not self.utils.exists(spec_file):
            self.utils.write_text(spec_file, render_walk_spec(cls_name, node_names))
        self.utils.write_text(
            test_file, render_walk_test(pkg, name, cls_name, node_names[0])
        )

        self.utils.print(f"Created {walk_file}")
        self.utils.print(f"Created {test_file}")
        self.utils.print(f"Created {spec_file}")
        return Outcome.DONE

    def _fail(self, state: State, code: int, message: str) -> Outcome:
        self.utils.print_error(message)
        state.exit_code = code
        return Outcome.FAILED


def _parse_edges(items: list[str]) -> list[Edge]:
    """Parses ``node.OUTCOME=target`` items, ignoring malformed ones."""
    edges: list[Edge] = []
    for item in items:
        source, sep, target = item.partition("=")
        if sep and "." in source:
            src_node, src_outcome = source.split(".", 1)
            edges.append((to_snake(src_node), to_shout(src_outcome), to_snake(target)))
    return edges
