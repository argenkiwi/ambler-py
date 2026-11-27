from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Protocol

from ambler.nodes import HasArgv, HasExitCode
from ambler.utils.args import ArgParser, UsageError
from ambler.utils.fs import ProjectError
from ambler.utils.fs import ScaffoldUtils as Utils
from ambler.utils.fs import SystemScaffoldUtils as SystemUtils
from ambler.utils.naming import to_pascal, to_shout, to_snake
from ambler.utils.source import (
    Imports,
    NodeInfo,
    Protocols,
    SourceError,
    read_node,
    read_protocols,
)
from ambler.utils.templates import (
    Edges,
    StateField,
    add_script,
    render_walk,
    render_walk_spec,
    render_walk_test,
)

NODE_USAGE = (
    "(--outcomes <a,b> | --terminal) [--fallible] [--state <field>[:<Type>]]..."
)


class Outcome(Enum):
    """Whether the walk was written."""

    DONE = auto()
    FAILED = auto()


class State(HasArgv, HasExitCode, Protocol):
    pass


class Rejected(Exception):
    """Why the walk cannot be written, and the exit code that says so."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ScaffoldWalk:
    """Reads the walk's nodes and writes ``src/<pkg>/walks/<name>.py``, its wiring
    test, ``specs/<name>.md`` when that does not exist yet, and its script."""

    utils: Utils = field(default_factory=SystemUtils)

    async def run(self, state: State) -> Outcome:
        try:
            self._scaffold(state.argv)
        except Rejected as e:
            self.utils.print_error(f"Error: {e}")
            state.exit_code = e.code
            return Outcome.FAILED
        return Outcome.DONE

    def _scaffold(self, argv: list[str]) -> None:
        parser = ArgParser()
        parser.add_argument("name")
        parser.add_argument("--nodes", required=True)
        parser.add_argument("--edge", action="append")
        parser.add_argument("--no-runner", action="store_true")
        try:
            args = parser.parse_args(argv)
        except UsageError as e:
            raise Rejected(2, str(e)) from e

        names = [to_snake(n.strip()) for n in args.nodes.split(",") if n.strip()]
        if not names:
            raise Rejected(2, "--nodes must contain at least one node name")

        try:
            pkg = self.utils.package_name()
        except ProjectError as e:
            raise Rejected(1, str(e)) from e

        name = to_snake(args.name)
        root = self.utils.root()
        nodes_dir = root / "src" / pkg / "nodes"
        walk_file = root / "src" / pkg / "walks" / f"{name}.py"
        test_file = root / "tests" / "walks" / f"test_{name}.py"
        spec_file = root / "specs" / f"{name}.md"
        pyproject_file = root / "pyproject.toml"

        if self.utils.exists(walk_file):
            raise Rejected(1, f"Walk {name} already exists at {walk_file}")

        missing = [n for n in names if not self.utils.exists(nodes_dir / f"{n}.py")]
        if missing:
            commands = "\n".join(
                f"  uv run ambler node {n} {NODE_USAGE}" for n in missing
            )
            raise Rejected(
                2,
                "the walk needs nodes that do not exist yet. Create them first:\n"
                + commands,
            )

        init_file = nodes_dir / "__init__.py"
        try:
            protocols = (
                read_protocols(self.utils.read_text(init_file), pkg)
                if self.utils.exists(init_file)
                else Protocols({}, {})
            )
            nodes = [
                read_node(
                    self.utils.read_text(nodes_dir / f"{n}.py"), n, to_pascal(n), pkg
                )
                for n in names
            ]
        except SourceError as e:
            raise Rejected(2, str(e)) from e

        edges = _edges(args.edge or [], nodes)
        fields, field_imports = _fields(nodes, protocols)

        pyproject = None
        if not args.no_runner:
            pyproject = add_script(
                self.utils.read_text(pyproject_file), name, f"{pkg}.walks.{name}:main"
            )
            if pyproject is None:
                raise Rejected(1, f"pyproject.toml already has a `{name}` script")

        cls_name = to_pascal(name)
        for path in (walk_file, test_file, spec_file):
            self.utils.mkdir(path.parent)
        self.utils.write_text(
            walk_file,
            render_walk(pkg, name, cls_name, nodes, edges, fields, field_imports),
        )
        self.utils.write_text(test_file, render_walk_test(pkg, name, cls_name, nodes))
        self.utils.format([walk_file, test_file])
        self.utils.print(f"Created {walk_file}")
        self.utils.print(f"Created {test_file}")
        if not self.utils.exists(spec_file):
            self.utils.write_text(
                spec_file, render_walk_spec(name, nodes, edges, fields)
            )
            self.utils.print(f"Created {spec_file}")
        if pyproject is not None:
            self.utils.write_text(pyproject_file, pyproject)
            self.utils.print(
                f"Added the `{name}` script to pyproject.toml: "
                f"run `uv sync`, then `uv run {name}`."
            )


def _edges(items: list[str], nodes: list[NodeInfo]) -> Edges:
    """Parses ``node.OUTCOME=target`` items, repeated or separated by commas."""
    by_name = {node.name: node for node in nodes}
    edges: Edges = {}
    for item in (part.strip() for raw in items for part in raw.split(",")):
        if not item:
            continue
        source, sep, target = item.partition("=")
        node_name, dot, outcome = source.partition(".")
        if not (sep and dot and node_name and outcome and target):
            raise Rejected(
                2, f"malformed edge `{item}`: use <node>.<OUTCOME>=<node|halt>"
            )
        node_name, outcome, target = (
            to_snake(node_name),
            to_shout(outcome),
            to_snake(target),
        )
        node = by_name.get(node_name)
        if node is None:
            raise Rejected(2, f"edge `{item}`: `{node_name}` is not a node of the walk")
        if node.outcomes is None:
            raise Rejected(
                2, f"edge `{item}`: `{node_name}` ends the walk; it has no outcomes"
            )
        if outcome not in node.outcomes:
            known = ", ".join(node.outcomes)
            raise Rejected(
                2, f"edge `{item}`: `{node_name}` has no outcome {outcome} ({known})"
            )
        if target != "halt" and target not in by_name:
            raise Rejected(2, f"edge `{item}`: `{target}` is not a node of the walk")
        edges[(node_name, outcome)] = target
    return edges


def _fields(
    nodes: list[NodeInfo], protocols: Protocols
) -> tuple[list[StateField], Imports]:
    """Every field the nodes' protocols declare, in order, and the imports their
    types need."""
    fields: dict[str, str] = {}
    imports = Imports()
    for node in nodes:
        if node.outcomes == ():
            raise Rejected(2, f"`{node.name}` has an `Outcome` with no members")
        for protocol in node.protocols:
            if protocol not in protocols.fields:
                raise Rejected(
                    2,
                    f"`{node.name}` needs `{protocol}`, which the nodes package lacks",
                )
            imports.update(protocols.imports[protocol])
            for f, t in protocols.fields[protocol]:
                if fields.setdefault(f, t) != t:
                    raise Rejected(
                        2,
                        f"nodes give the state field `{f}` different types: "
                        f"{fields[f]} and {t}",
                    )
    return list(fields.items()), imports
