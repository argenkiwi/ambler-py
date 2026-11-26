import ast
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Protocol

from ambler.nodes import HasArgv, HasExitCode
from ambler.utils.args import ArgParser, UsageError
from ambler.utils.fs import ProjectError
from ambler.utils.fs import ScaffoldUtils as Utils
from ambler.utils.fs import SystemScaffoldUtils as SystemUtils
from ambler.utils.naming import to_pascal, to_shout, to_snake
from ambler.utils.source import Imports, Protocols, SourceError, read_protocols
from ambler.utils.templates import (
    PACKAGE_INIT,
    StateField,
    protocol_name,
    render_node,
    render_node_test,
    render_protocols,
)


class Outcome(Enum):
    """Whether the node was written."""

    DONE = auto()
    FAILED = auto()


class State(HasArgv, HasExitCode, Protocol):
    pass


@dataclass(frozen=True)
class ScaffoldNode:
    """Writes ``src/<pkg>/nodes/<name>.py`` and its test, plus any missing ``Has*``
    state protocols."""

    utils: Utils = field(default_factory=SystemUtils)

    async def run(self, state: State) -> Outcome:
        parser = ArgParser()
        parser.add_argument("name")
        parser.add_argument("--outcomes")
        parser.add_argument("--terminal", action="store_true")
        parser.add_argument("--fallible", action="store_true")
        parser.add_argument("--state", action="append")
        try:
            args = parser.parse_args(state.argv)
        except UsageError as e:
            return self._fail(state, 2, f"Error: {e}")

        try:
            pkg = self.utils.package_name()
        except ProjectError as e:
            return self._fail(state, 1, f"Error: {e}")

        name = to_snake(args.name)
        root = self.utils.root()
        nodes_dir = root / "src" / pkg / "nodes"
        tests_dir = root / "tests" / "nodes"
        node_file = nodes_dir / f"{name}.py"
        test_file = tests_dir / f"test_{name}.py"

        if self.utils.exists(node_file):
            return self._fail(
                state, 1, f"Error: Node {name} already exists at {node_file}"
            )

        terminal: bool = args.terminal
        outcomes = [
            to_shout(o.strip()) for o in (args.outcomes or "").split(",") if o.strip()
        ]
        if not terminal and not outcomes:
            return self._fail(
                state, 2, "Error: Specify either --outcomes <a,b> or --terminal"
            )

        init_file = nodes_dir / "__init__.py"
        init_content = (
            self.utils.read_text(init_file)
            if self.utils.exists(init_file)
            else PACKAGE_INIT
        )
        try:
            state_fields, imports = _resolve_state_fields(
                args.state or [], read_protocols(init_content, pkg)
            )
        except (SourceError, ValueError) as e:
            return self._fail(state, 2, f"Error: {e}")
        cls_name = to_pascal(name)

        self.utils.mkdir(nodes_dir)
        self.utils.mkdir(tests_dir)

        updated = render_protocols(init_content, state_fields)
        if updated != init_content:
            self.utils.write_text(init_file, updated)

        fallible: bool = args.fallible
        self.utils.write_text(
            node_file,
            render_node(
                pkg,
                cls_name,
                terminal=terminal,
                fallible=fallible,
                outcomes=outcomes,
                state_fields=state_fields,
            ),
        )
        self.utils.write_text(
            test_file,
            render_node_test(
                pkg,
                name,
                cls_name,
                terminal=terminal,
                fallible=fallible,
                outcomes=outcomes,
                state_fields=state_fields,
                imports=imports,
            ),
        )

        self.utils.print(f"Created {node_file}")
        self.utils.print(f"Created {test_file}")
        return Outcome.DONE

    def _fail(self, state: State, code: int, message: str) -> Outcome:
        self.utils.print_error(message)
        state.exit_code = code
        return Outcome.FAILED


def _normalise(type_text: str, field_name: str) -> str:
    """``type_text`` as ``ast.unparse`` writes it, so equal types compare equal."""
    try:
        return ast.unparse(ast.parse(type_text, mode="eval"))
    except SyntaxError as e:
        raise ValueError(f"`{type_text}` is not a type for `{field_name}`") from e


def _resolve_state_fields(
    items: list[str], protocols: Protocols
) -> tuple[list[StateField], Imports]:
    """Parses ``name[:type]`` items against the existing ``Has*`` protocols.

    A field without a type reuses its protocol's type, and the imports that type
    needs. A field with a type must match its protocol, if it has one.

    Raises:
        ValueError: if a field has no type and no protocol, or a different type
            from its protocol's.
    """
    fields: list[StateField] = []
    imports = Imports()
    for item in items:
        raw_name, has_type, raw_type = item.partition(":")
        f_name = to_snake(raw_name.strip())
        protocol = protocol_name(f_name)
        existing = dict(protocols.fields.get(protocol, [])).get(f_name)
        if not has_type:
            if existing is None:
                raise ValueError(
                    f"no node declares `{f_name}` yet, so `--state {f_name}` needs "
                    f"its type: use `--state {f_name}:<Type>`"
                )
            f_type = existing
        else:
            f_type = _normalise(raw_type.strip(), f_name)
            if existing is not None and existing != f_type:
                raise ValueError(
                    f"`{f_name}` is already declared as `{existing}` in "
                    f"nodes/__init__.py, not `{f_type}`: use `--state {f_name}` "
                    "to reuse it"
                )
        if existing is not None:
            imports.update(protocols.imports[protocol])
        fields.append((f_name, f_type))
    return fields, imports
