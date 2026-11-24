"""Pure source-code templates for the scaffolding nodes."""

from ambler.utils.naming import to_pascal, to_shout

NOT_IMPLEMENTED_MARKER = f"{'not yet'} {'implemented'}"

StateField = tuple[str, str]
"""A state field as ``(name, type)``."""

Edge = tuple[str, str, str]
"""A walk transition as ``(node, OUTCOME, target)``."""

PACKAGE_INIT = '"""Node package."""\n\nfrom typing import Protocol\n'


def protocol_name(field_name: str) -> str:
    return f"Has{to_pascal(field_name)}"


def render_protocols(init_content: str, state_fields: list[StateField]) -> str:
    """Appends a ``Has*`` protocol for every state field not yet declared.

    Returns ``init_content`` unchanged when nothing is missing.
    """
    for f_name, f_type in state_fields:
        p_name = protocol_name(f_name)
        if p_name not in init_content:
            if "from typing import Protocol" not in init_content:
                init_content = "from typing import Protocol\n\n" + init_content
            doc = f'"""A state that has a {f_name} field."""'
            init_content += (
                f"\n\nclass {p_name}(Protocol):\n    {doc}\n\n    {f_name}: {f_type}\n"
            )
    return init_content


def render_node(
    pkg: str,
    cls_name: str,
    *,
    terminal: bool,
    fallible: bool,
    outcomes: list[str],
    state_fields: list[StateField],
) -> str:
    protocols = [protocol_name(n) for n, _ in state_fields]
    lines: list[str] = [
        "from dataclasses import dataclass, field",
    ]
    if not terminal:
        lines.append("from enum import Enum, auto")
    lines.append("from typing import Protocol")
    if protocols:
        lines.append(f"from {pkg}.nodes import {', '.join(protocols)}")

    lines.append("\n")

    if not terminal:
        lines.append(
            'class Outcome(Enum):\n    """Where this node leaves the walk."""\n'
        )
        for out in outcomes:
            lines.append(f"    {out} = auto()\n")
        lines.append("\n")

    if fallible:
        lines.append(
            'class Error(Exception):\n    """What stops this node from finishing."""\n'
        )

    if not protocols:
        state_type = "object"
    elif len(protocols) == 1:
        state_type = protocols[0]
    else:
        lines.append(f"class State({', '.join(protocols)}, Protocol):\n    pass\n\n")
        state_type = "State"

    ret_type = "None" if terminal else "Outcome"

    lines.append(f'''class Utils(Protocol):
    """The side effects this node needs: one method each, faked in the tests."""


class SystemUtils:
    """The real side effects."""


@dataclass(frozen=True)
class {cls_name}:
    """Atomic step node."""

    utils: Utils = field(default_factory=SystemUtils)

    async def run(self, state: {state_type}) -> {ret_type}:
        raise NotImplementedError("{NOT_IMPLEMENTED_MARKER}")
''')

    return "\n".join(lines) + "\n"


def render_node_test(
    pkg: str,
    name: str,
    cls_name: str,
    *,
    terminal: bool,
    fallible: bool,
    outcomes: list[str],
    state_fields: list[StateField],
) -> str:
    t_lines: list[str] = [
        "from dataclasses import dataclass\n",
    ]
    if fallible:
        t_lines.append("import pytest\n")

    imports = [cls_name]
    if not terminal:
        imports.append("Outcome")
    if fallible:
        imports.append("Error")
    t_lines.append(f"from {pkg}.nodes.{name} import {', '.join(imports)}\n\n")

    if state_fields:
        t_lines.append("@dataclass\nclass MockState:\n")
        for fn, ft in state_fields:
            default_val = (
                "0"
                if ft == "int"
                else '""'
                if ft == "str"
                else "False"
                if ft == "bool"
                else "None"
            )
            t_lines.append(f"    {fn}: {ft} = {default_val}\n")
    else:
        t_lines.append("@dataclass\nclass MockState:\n    pass\n")

    t_lines.append('''
class MockUtils:
    """Fakes every side effect of the node."""


''')

    if terminal:
        t_lines.append(f"""async def test_finishes() -> None:
    state = MockState()
    await {cls_name}(MockUtils()).run(state)
""")
    else:
        for out in outcomes:
            t_lines.append(f"""async def test_{out.lower()}_when_pending() -> None:
    state = MockState()
    outcome = await {cls_name}(MockUtils()).run(state)
    assert outcome == Outcome.{out}
""")

    return "\n".join(t_lines) + "\n"


def render_walk(
    pkg: str, name: str, cls_name: str, node_names: list[str], edges: list[Edge]
) -> str:
    lines: list[str] = [
        '"""Walk implementation."""\n',
        "from dataclasses import dataclass, field",
        "from enum import Enum, auto\n",
        f"from {pkg} import Walk",
    ]
    for n in node_names:
        lines.append(f"from {pkg}.nodes.{n} import {to_pascal(n)}")

    lines.append("\n\n@dataclass\nclass State:\n    pass\n\n\nclass Id(Enum):\n")
    for n in node_names:
        lines.append(f"    {to_shout(n)} = auto()\n")

    lines.append(f"\n\n@dataclass(frozen=True)\nclass {cls_name}(Walk[Id, State]):\n")
    for n in node_names:
        p_name = to_pascal(n)
        lines.append(f"    {n}: {p_name} = field(default_factory={p_name})\n")

    lines.append("\n    async def step(self, id: Id, state: State) -> Id | None:\n")
    lines.append("        match id:\n")
    for n in node_names:
        lines.append(f"            case Id.{to_shout(n)}:\n")
        matched_edges = [edge for edge in edges if edge[0] == n]
        if matched_edges:
            lines.append(f"                match await self.{n}.run(state):\n")
            for _, outcome, tgt in matched_edges:
                tgt_return = f"Id.{to_shout(tgt)}" if tgt.lower() != "halt" else "None"
                lines.append(
                    f"                    case {to_pascal(n)}.Outcome.{outcome}:\n"
                )
                lines.append(f"                        return {tgt_return}\n")
        else:
            lines.append(f"                # Wire outcomes for {n}\n")
            lines.append(f"                await self.{n}.run(state)\n")
            lines.append("                return None\n")

    lines.append(f'''

async def run() -> None:
    """Runs the {name} walk."""
    await {cls_name}().run(Id.{to_shout(node_names[0])}, State())
''')

    return "".join(lines)


def render_walk_test(pkg: str, name: str, cls_name: str, first_node: str) -> str:
    return f"""import pytest
from {pkg}.walks.{name} import {cls_name}, Id, State


async def test_{name}_walk_initial_step() -> None:
    walk = {cls_name}()
    state = State()
    next_id = await walk.step(Id.{to_shout(first_node)}, state)
    assert next_id is None or isinstance(next_id, Id)
"""


def render_walk_spec(cls_name: str, node_names: list[str]) -> str:
    return f"""# {cls_name} Walk Specification

Initial node: `{node_names[0]}`.

## Flow
{" -> ".join(node_names)}
"""


def render_util(name: str, cls_name: str) -> str:
    return f'''"""Utility module {name}."""

from typing import Protocol


class {cls_name}Utils(Protocol):
    """Protocol for {name} operations."""


class System{cls_name}Utils:
    """Production implementation."""
'''
