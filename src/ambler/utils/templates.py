"""Pure source-code templates for the scaffolding nodes."""

import re
import sys

from ambler.utils.naming import to_pascal, to_shout
from ambler.utils.source import Imports, NodeInfo

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


def _type_order(name: str) -> tuple[int, str]:
    """isort's order within a from-import: constants, then classes, then the rest."""
    base = name.split(" as ")[0]
    kind = 0 if base.isupper() and len(base) > 1 else 1 if base[:1].isupper() else 2
    return kind, base.lower()


def _names(names: list[str] | set[str]) -> str:
    return ", ".join(sorted(names, key=_type_order))


def _section(module: str, pkg: str) -> int:
    top = module.split(".")[0]
    if top == pkg:
        return 2
    return 0 if top in sys.stdlib_module_names or top == "__future__" else 1


def render_imports(pkg: str, imports: Imports) -> str:
    """``imports`` as the standard library, third-party and package sections."""
    sections: list[list[str]] = [[], [], []]
    for module in sorted(imports.plain):
        sections[_section(module, pkg)].append(f"import {module}")
    for module in sorted(imports.from_):
        line = f"from {module} import {_names(imports.from_[module])}"
        sections[_section(module, pkg)].append(line)
    return "\n\n".join("\n".join(section) for section in sections if section)


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
    fields = "\n".join(
        f"    {fn}: {ft} = {state_default(ft)}" for fn, ft in state_fields
    )
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
            [
                "from dataclasses import dataclass, field"
                if "field(" in fields
                else "from dataclasses import dataclass"
            ],
            [f"from {pkg}.nodes.{name} import {_names(imports)}"],
        ),
        mock_state,
        '''class MockUtils:
    """Fakes every side effect of the node."""''',
        *tests,
    )


Edges = dict[tuple[str, str], str]
"""Where each ``(node, OUTCOME)`` leads: a node, or ``halt``."""


def state_default(field_type: str) -> str:
    """A default for a ``State`` field of ``field_type``."""
    simple = {"int": "0", "float": "0.0", "str": '""', "bool": "False", "bytes": 'b""'}
    if field_type in simple:
        return simple[field_type]
    if re.search(r"(^|\|)\s*None\s*($|\|)", field_type) or field_type.startswith(
        "Optional["
    ):
        return "None"
    return f"field(default_factory={field_type})"


def _title(name: str) -> str:
    return " ".join(part.capitalize() for part in name.split("_") if part)


def _arm(node: NodeInfo, edges: Edges) -> str:
    head = f"            case Id.{to_shout(node.name)}:"
    if node.outcomes is None:
        run = f"                await self.{node.name}.run(state)"
        return f"{head}\n{run}\n                return None"
    lines = [head, f"                match await self.{node.name}.run(state):"]
    for outcome in node.outcomes:
        lines.append(f"                    case {node.name}.Outcome.{outcome}:")
        target = edges.get((node.name, outcome))
        if target is None:
            wire = f"{to_shout(node.name)}.{outcome}"
            lines.append(
                f'{" " * 24}raise NotImplementedError("not yet wired: {wire}")'
            )
        elif target == "halt":
            lines.append("                        return None")
        else:
            lines.append(f"                        return Id.{to_shout(target)}")
    return "\n".join(lines)


def render_walk(
    pkg: str,
    name: str,
    cls_name: str,
    nodes: list[NodeInfo],
    edges: Edges,
    fields: list[StateField],
    field_imports: Imports,
) -> str:
    fallible = [node for node in nodes if node.fallible]
    imports = Imports(plain={"asyncio"})
    if fallible:
        imports.plain.add("sys")
    for module, names in (("dataclasses", "dataclass field"), ("enum", "Enum auto")):
        for imported in names.split():
            imports.add_from(module, imported)
    imports.add_from(f"{pkg}.engine", "Walk")
    for node in nodes:
        if node.outcomes is not None or node.fallible:
            imports.add_from(f"{pkg}.nodes", node.name)
        imports.add_from(f"{pkg}.nodes.{node.name}", node.cls_name)
    imports.update(field_imports)

    exported = ["Error", "main", "run"] if fallible else ["main", "run"]
    surface = "__all__ = [" + ", ".join(f'"{e}"' for e in exported) + "]"
    if fallible:
        errors = [f"{node.name}.Error" for node in fallible]
        value = errors[0] if len(errors) == 1 else f"({', '.join(errors)})"
        surface += f'\n\nError = {value}\n"""What can stop the walk early."""'

    state = "\n".join(f"    {f}: {t} = {state_default(t)}" for f, t in fields)
    ids = "\n".join(f"    {to_shout(node.name)} = auto()" for node in nodes)
    members = "\n".join(
        f"    {node.name}: {node.cls_name} = field(default_factory={node.cls_name})"
        for node in nodes
    )
    arms = "\n".join(_arm(node, edges) for node in nodes)
    start = f"Id.{to_shout(nodes[0].name)}"
    reported = (
        "    try:\n        asyncio.run(run())\n    except Error as e:\n"
        '        sys.exit(f"Error: {e}")'
        if fallible
        else "    asyncio.run(run())"
    )

    return _module(
        f'"""The {name} walk: see ``specs/{name}.md``."""\n\n'
        + render_imports(pkg, imports),
        surface,
        f"@dataclass\nclass State:\n{state or '    pass'}",
        f"class Id(Enum):\n{ids}",
        f"""@dataclass(frozen=True)
class {cls_name}(Walk[Id, State]):
{members}

    async def step(self, id: Id, state: State) -> Id | None:
        match id:
{arms}""",
        f'''async def run() -> None:
    """Runs the walk from its first node."""
    await {cls_name}().run({start}, State())''',
        f'''def main() -> None:
    """Runs the walk: the ``{name}`` script in pyproject.toml."""
{reported}''',
    )


def render_walk_test(pkg: str, name: str, cls_name: str, nodes: list[NodeInfo]) -> str:
    imports = Imports()
    methods: dict[str, str] = {}
    for node in nodes:
        imports.add_from(f"{pkg}.nodes.{node.name}", node.cls_name)
        imports.update(node.imports)
        for method in node.utils:
            match = re.search(r"def (\w+)", method)
            if match:
                methods.setdefault(match.group(1), method)
    for exported in (cls_name, "Id", "State"):
        imports.add_from(f"{pkg}.walks.{name}", exported)

    script = '''class Script:
    """Stands in for every node's utils: plays back inputs and records effects."""'''
    if methods:
        script += "\n\n" + "\n\n".join(methods.values())
    walk = ", ".join(f"{node.name}={node.cls_name}(script)" for node in nodes)
    first = nodes[0].name

    return _module(
        f'"""The wiring of the {name} walk: one test per path through it."""\n\n'
        + render_imports(pkg, imports),
        script,
        f"""async def test_{name}_walks_from_{first}() -> None:
    script = Script()
    state = State()

    await {cls_name}({walk}).run(Id.{to_shout(first)}, state)

    raise NotImplementedError("{NOT_IMPLEMENTED_MARKER}")""",
    )


def render_walk_spec(
    name: str, nodes: list[NodeInfo], edges: Edges, fields: list[StateField]
) -> str:
    sections: list[str] = []
    for index, node in enumerate(nodes):
        lines = [f"### {_title(node.name)}"]
        if index == 0:
            lines.append("- Initial node.")
        lines.append("- <What it does.>")
        if node.outcomes is None:
            lines.append("- Terminates.")
        for outcome in node.outcomes or ():
            target = edges.get((node.name, outcome))
            if target is None:
                lines.append(f"- If `{outcome}`, <where it leads: not wired yet>.")
            elif target == "halt":
                lines.append(f"- If `{outcome}`, it terminates.")
            else:
                lines.append(
                    f"- If `{outcome}`, it transitions to `{to_shout(target)}`."
                )
        sections.append("\n".join(lines))
    state = "\n".join(f"- `{f}`: <what it holds>." for f, _ in fields)
    return (
        "# Program Specifications\n\n"
        f"<What the {name} walk is for, in a sentence or two.>\n\n"
        "## Nodes\n\n"
        + "\n\n".join(sections)
        + "\n\n## Shared State\n\n"
        + (
            f"The shared state consists of:\n{state}\n"
            if state
            else "The shared state is empty.\n"
        )
    )


def add_script(pyproject: str, name: str, target: str) -> str | None:
    """``pyproject`` with a ``name`` script running ``target`` in ``[project.scripts]``,
    in alphabetical order, or ``None`` if there is already a script called ``name``."""
    entry = f'{name} = "{target}"\n'
    lines = pyproject.splitlines(keepends=True)
    header = next(
        (i for i, line in enumerate(lines) if line.strip() == "[project.scripts]"), None
    )
    if header is None:
        return pyproject.rstrip("\n") + f"\n\n[project.scripts]\n{entry}"
    at = header + 1
    for i in range(header + 1, len(lines)):
        line = lines[i].strip()
        if line.startswith("["):
            break
        if "=" not in line:
            continue
        key = line.split("=", 1)[0].strip().strip('"')
        if key == name:
            return None
        if key < name:
            at = i + 1
    return "".join([*lines[:at], entry, *lines[at:]])


def render_util(name: str, cls_name: str) -> str:
    return f'''"""Utility module {name}."""

from typing import Protocol


class {cls_name}Utils(Protocol):
    """Protocol for {name} operations."""


class System{cls_name}Utils:
    """Production implementation."""
'''
