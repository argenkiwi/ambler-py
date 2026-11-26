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


def _module(*blocks: str) -> str:
    """Top-level ``blocks`` two blank lines apart, as ``ruff format`` writes them."""
    return "\n\n\n".join(block.strip("\n") for block in blocks if block) + "\n"


def _imports(stdlib: list[str], first_party: list[str]) -> str:
    """Import groups in the order ``ruff check``'s isort rules expect."""
    groups = [sorted(stdlib), sorted(first_party)]
    return "\n\n".join("\n".join(group) for group in groups if group)


def _names(names: list[str]) -> str:
    return ", ".join(sorted(names))


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
    stdlib = ["from dataclasses import dataclass, field", "from typing import Protocol"]
    if not terminal:
        stdlib.append("from enum import Enum, auto")
    first_party = [f"from {pkg}.nodes import {_names(protocols)}"] if protocols else []

    outcome = ""
    if not terminal:
        members = "\n".join(f"    {out} = auto()" for out in outcomes)
        outcome = f'''class Outcome(Enum):
    """Where this node leaves the walk."""

{members}'''

    error = (
        '''class Error(Exception):
    """What stops this node from finishing."""'''
        if fallible
        else ""
    )

    if not protocols:
        state_type, state = "object", ""
    elif len(protocols) == 1:
        state_type, state = protocols[0], ""
    else:
        state_type = "State"
        state = f"class State({', '.join(protocols)}, Protocol):\n    pass"

    ret_type = "None" if terminal else "Outcome"

    return _module(
        _imports(stdlib, first_party),
        outcome,
        error,
        state,
        '''class Utils(Protocol):
    """The side effects this node needs: one method each, faked in the tests."""''',
        '''class SystemUtils:
    """The real side effects."""''',
        f'''@dataclass(frozen=True)
class {cls_name}:
    """Atomic step node."""

    utils: Utils = field(default_factory=SystemUtils)

    async def run(self, state: {state_type}) -> {ret_type}:
        raise NotImplementedError("{NOT_IMPLEMENTED_MARKER}")''',
    )


def _default(field_type: str) -> str:
    return {"int": "0", "str": '""', "bool": "False"}.get(field_type, "None")


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
    imports = [cls_name] if terminal else [cls_name, "Outcome"]
    fields = "\n".join(f"    {fn}: {ft} = {_default(ft)}" for fn, ft in state_fields)
    mock_state = f"@dataclass\nclass MockState:\n{fields or '    pass'}"

    if terminal:
        tests = [
            f"""async def test_finishes() -> None:
    state = MockState()
    await {cls_name}(MockUtils()).run(state)"""
        ]
    else:
        tests = [
            f"""async def test_{out.lower()}_when_pending() -> None:
    state = MockState()
    outcome = await {cls_name}(MockUtils()).run(state)
    assert outcome == Outcome.{out}"""
            for out in outcomes
        ]

    return _module(
        _imports(
            ["from dataclasses import dataclass"],
            [f"from {pkg}.nodes.{name} import {_names(imports)}"],
        ),
        mock_state,
        '''class MockUtils:
    """Fakes every side effect of the node."""''',
        *tests,
    )


def render_walk(
    pkg: str, name: str, cls_name: str, node_names: list[str], edges: list[Edge]
) -> str:
    first_party = [f"from {pkg} import Walk"] + [
        f"from {pkg}.nodes.{n} import {to_pascal(n)}" for n in node_names
    ]
    ids = "\n".join(f"    {to_shout(n)} = auto()" for n in node_names)
    fields = "\n".join(
        f"    {n}: {to_pascal(n)} = field(default_factory={to_pascal(n)})"
        for n in node_names
    )

    arms: list[str] = []
    for n in node_names:
        arms.append(f"            case Id.{to_shout(n)}:")
        matched_edges = [edge for edge in edges if edge[0] == n]
        if matched_edges:
            arms.append(f"                match await self.{n}.run(state):")
            for _, outcome, tgt in matched_edges:
                tgt_return = f"Id.{to_shout(tgt)}" if tgt.lower() != "halt" else "None"
                arms.append(
                    f"                    case {to_pascal(n)}.Outcome.{outcome}:"
                )
                arms.append(f"                        return {tgt_return}")
        else:
            arms.append(f"                # Wire outcomes for {n}")
            arms.append(f"                await self.{n}.run(state)")
            arms.append("                return None")
    step = "\n".join(arms)

    return _module(
        '"""Walk implementation."""\n\n'
        + _imports(
            ["from dataclasses import dataclass, field", "from enum import Enum, auto"],
            first_party,
        ),
        "@dataclass\nclass State:\n    pass",
        f"class Id(Enum):\n{ids}",
        f"""@dataclass(frozen=True)
class {cls_name}(Walk[Id, State]):
{fields}

    async def step(self, id: Id, state: State) -> Id | None:
        match id:
{step}""",
        f'''async def run() -> None:
    """Runs the {name} walk."""
    await {cls_name}().run(Id.{to_shout(node_names[0])}, State())''',
    )


def render_walk_test(pkg: str, name: str, cls_name: str, first_node: str) -> str:
    return _module(
        f"from {pkg}.walks.{name} import {_names([cls_name, 'Id', 'State'])}",
        f"""async def test_{name}_walk_initial_step() -> None:
    walk = {cls_name}()
    state = State()
    next_id = await walk.step(Id.{to_shout(first_node)}, state)
    assert next_id is None or isinstance(next_id, Id)""",
    )


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
