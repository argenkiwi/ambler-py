"""The structural conventions ``check`` verifies before running the tools.

Pure functions over source text: each returns ``<path>:<line>: <rule>: <what to do>``
lines, one per violation.
"""

import ast
import re
from pathlib import PurePosixPath

from ambler.utils.naming import to_pascal

# Built in pieces so that this module is not itself a placeholder the rule finds.
NOT_IMPLEMENTED = "not yet " + "implemented"
NOT_WIRED = "not yet " + "wired"


def _placeholder(node: ast.AST) -> str | None:
    """The message of ``raise NotImplementedError("<message>")``, if ``node`` is one."""
    if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
        return None
    call = node.exc
    if not (isinstance(call.func, ast.Name) and call.func.id == "NotImplementedError"):
        return None
    if not call.args or not isinstance(call.args[0], ast.Constant):
        return None
    message = call.args[0].value
    return message if isinstance(message, str) else None


def todo(path: str, source: str) -> list[str]:
    """The placeholders the scaffolders write that are still in ``source``: a body
    that raises ``not yet implemented`` or an outcome that raises ``not yet wired``.

    Only those ``raise`` statements count, not other mentions of the words. A file
    that does not parse is left to ruff and pyright to report.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        message = _placeholder(node)
        if message is None:
            continue
        line = getattr(node, "lineno", 0)
        if message == NOT_IMPLEMENTED:
            found.append((line, f"implement this: it still raises `{NOT_IMPLEMENTED}`"))
        elif message.startswith(f"{NOT_WIRED}: "):
            edge = message.removeprefix(f"{NOT_WIRED}: ")
            found.append(
                (line, f"wire {edge}: return the next `Id`, or `None` to end the walk")
            )
    return [f"{path}:{line}: todo: {what}" for line, what in sorted(found)]


CONTRACT = re.compile(r"Has[A-Z]\w*")
"""The name of a state contract: ``Has<PascalField>``."""


def _is_protocol(base: ast.expr) -> bool:
    return (isinstance(base, ast.Name) and base.id == "Protocol") or (
        isinstance(base, ast.Attribute) and base.attr == "Protocol"
    )


def _is_filler(stmt: ast.stmt) -> bool:
    """A docstring, ``pass`` or ``...``: a statement that declares nothing."""
    return isinstance(stmt, ast.Pass) or (
        isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
    )


def _members(cls: ast.ClassDef) -> list[tuple[int, str]]:
    """Each attribute or method ``cls`` declares, with its line."""
    found: list[tuple[int, str]] = []
    for stmt in cls.body:
        if isinstance(stmt, ast.AnnAssign | ast.Assign):
            targets = [stmt.target] if isinstance(stmt, ast.AnnAssign) else stmt.targets
            for target in targets:
                found.append((stmt.lineno, ast.unparse(target)))
        elif isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            found.append((stmt.lineno, stmt.name))
        elif not _is_filler(stmt):
            found.append((stmt.lineno, ast.unparse(stmt).splitlines()[0]))
    return found


def _registry_contract(cls: ast.ClassDef) -> list[tuple[int, str]]:
    """What is wrong with the ``Has*`` protocol ``cls`` in the state registry."""
    found: list[tuple[int, str]] = []
    others = [ast.unparse(b) for b in cls.bases if not _is_protocol(b)]
    if others:
        found.append(
            (
                cls.lineno,
                f"`{cls.name}` extends {', '.join(f'`{o}`' for o in others)}: a "
                "`Has*` protocol extends only `Protocol`; compose contracts in "
                "the node's local `State`",
            )
        )
    fields = [
        s
        for s in cls.body
        if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)
    ]
    extra = [
        (line, name)
        for line, name in _members(cls)
        if not any(f.lineno == line for f in fields)
    ]
    for line, name in extra:
        found.append(
            (
                line,
                f"`{cls.name}` declares `{name}`: a `Has*` protocol holds only "
                "one annotated field",
            )
        )
    if len(fields) != 1:
        names = ", ".join(f"`{ast.unparse(f.target)}`" for f in fields) or "none"
        found.append(
            (
                cls.lineno,
                f"`{cls.name}` has {len(fields)} fields ({names}): give each "
                "field its own `Has<Field>` protocol",
            )
        )
    elif isinstance(fields[0].target, ast.Name):
        field_name = fields[0].target.id
        expected = "Has" + to_pascal(field_name)
        if cls.name != expected:
            found.append(
                (
                    cls.lineno,
                    f"`{cls.name}` holds `{field_name}`: name it `{expected}`",
                )
            )
    return found


def _local_states(tree: ast.Module) -> list[ast.ClassDef]:
    """The node's local state protocols: ``State``, and any other local class
    that ``run`` takes as its state."""
    classes = {s.name: s for s in tree.body if isinstance(s, ast.ClassDef)}
    names = {"State"}
    for cls in classes.values():
        for stmt in cls.body:
            if (
                isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef)
                and stmt.name == "run"
                and len(stmt.args.args) >= 2
            ):
                annotation = stmt.args.args[1].annotation
                if isinstance(annotation, ast.Name):
                    names.add(annotation.id)
    return [
        classes[name]
        for name in sorted(names)
        if name in classes and not CONTRACT.fullmatch(name)
    ]


def _local_state(cls: ast.ClassDef) -> list[tuple[int, str]]:
    """What is wrong with the node-local state protocol ``cls``."""
    found: list[tuple[int, str]] = []
    others = [
        ast.unparse(b)
        for b in cls.bases
        if not _is_protocol(b)
        and not (isinstance(b, ast.Name) and CONTRACT.fullmatch(b.id))
    ]
    if others:
        found.append(
            (
                cls.lineno,
                f"`{cls.name}` extends {', '.join(f'`{o}`' for o in others)}: a "
                "node's state extends only `Has*` protocols and `Protocol`",
            )
        )
    for line, name in _members(cls):
        found.append(
            (
                line,
                f"`{cls.name}` declares `{name}`: declare the field as a "
                "`Has<Field>` protocol in `nodes/__init__.py` and extend it",
            )
        )
    return found


def state_protocols(path: str, source: str) -> list[str]:
    """Where ``source`` breaks the state contract convention.

    - ``Has*`` protocols are declared only in the state registry,
      ``src/<pkg>/nodes/__init__.py``.
    - Each holds exactly one annotated field ``f``, extends only ``Protocol`` and
      is named ``Has<F>``.
    - A node's local ``State`` (or whatever local class ``run`` takes) extends
      only ``Has*`` protocols and ``Protocol``, and declares nothing itself.

    A file that does not parse is left to ruff and pyright to report.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    parts = PurePosixPath(path).parts
    in_nodes = len(parts) == 4 and parts[0] == "src" and parts[2] == "nodes"
    registry = in_nodes and parts[3] == "__init__.py"

    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.ClassDef)
            and CONTRACT.fullmatch(node.name)
            and any(_is_protocol(b) for b in node.bases)
        ):
            continue
        if registry and node in tree.body:
            found += _registry_contract(node)
        else:
            found.append(
                (
                    node.lineno,
                    f"`{node.name}` is a state contract: declare it in "
                    "`nodes/__init__.py`, the only place `Has*` protocols live",
                )
            )
    if in_nodes and not registry:
        for cls in _local_states(tree):
            found += _local_state(cls)
    return [f"{path}:{line}: state-protocols: {what}" for line, what in sorted(found)]
