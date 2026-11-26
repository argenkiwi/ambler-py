"""Reads what a walk needs to know about its nodes from their source code.

Pure functions over source text: nothing here touches the file system.
"""

import ast
import builtins
from dataclasses import dataclass, field

BUILTINS = frozenset(dir(builtins))


class SourceError(Exception):
    """A node or the nodes package does not have the shape a walk can be built from."""


@dataclass
class Imports:
    """Import statements, merged by module: ``from_`` maps a module to its names."""

    from_: dict[str, set[str]] = field(default_factory=dict[str, set[str]])
    plain: set[str] = field(default_factory=set[str])

    def add_from(self, module: str, name: str) -> None:
        self.from_.setdefault(module, set()).add(name)

    def update(self, other: "Imports") -> None:
        for module, names in other.from_.items():
            for name in names:
                self.add_from(module, name)
        self.plain |= other.plain


Origins = dict[str, tuple[str | None, str]]
"""Where each module-level name comes from: ``(module, name)`` for a from-import,
``(None, name)`` for a plain import, and ``(here, name)`` if defined here."""


@dataclass(frozen=True)
class Protocols:
    """The ``Has*`` protocols of the nodes package and their ``(name, type)`` fields."""

    fields: dict[str, list[tuple[str, str]]]
    imports: dict[str, Imports]
    """For each protocol, the imports its field types need."""
    origins: Origins = field(default_factory=Origins)
    """Where each name the nodes package binds comes from."""


@dataclass(frozen=True)
class NodeInfo:
    name: str
    cls_name: str
    outcomes: tuple[str, ...] | None
    """The members of ``Outcome``, or ``None`` if ``run`` returns ``None``."""
    fallible: bool
    protocols: tuple[str, ...]
    utils: tuple[str, ...]
    """Each ``Utils`` method as a ``Script`` method that is not yet implemented."""
    imports: Imports
    """What the ``Utils`` signatures need imported."""


def _names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _origins(tree: ast.Module, here: str) -> Origins:
    """Where each module-level name of ``tree`` comes from."""
    origins: Origins = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.ImportFrom) and stmt.module and stmt.level == 0:
            for alias in stmt.names:
                origins[alias.asname or alias.name] = (stmt.module, alias.name)
        elif isinstance(stmt, ast.Import):
            for alias in stmt.names:
                # ``import a.b`` binds ``a``; ``import a.b as c`` binds ``c``.
                bound = alias.asname or alias.name.split(".")[0]
                origins[bound] = (None, alias.name)
        elif isinstance(stmt, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            origins[stmt.name] = (here, stmt.name)
        elif isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.TypeAlias)):
            targets: list[ast.expr]
            if isinstance(stmt, ast.Assign):
                targets = stmt.targets
            elif isinstance(stmt, ast.AnnAssign):
                targets = [stmt.target]
            else:
                targets = [stmt.name]
            for target in targets:
                if isinstance(target, ast.Name):
                    origins[target.id] = (here, target.id)
    return origins


def _imports_for(names: set[str], origins: Origins) -> Imports:
    imports = Imports()
    for name in sorted(names - BUILTINS):
        origin = origins.get(name)
        if origin is None:
            continue
        module, original = origin
        if module is None:
            if original.split(".")[0] == name:
                imports.plain.add(original)
            else:
                imports.plain.add(f"{original} as {name}")
        elif original == name:
            imports.add_from(module, name)
        else:
            imports.add_from(module, f"{original} as {name}")
    return imports


def _parse(source: str, what: str) -> ast.Module:
    try:
        return ast.parse(source)
    except SyntaxError as e:
        raise SourceError(f"{what} is not valid Python: {e}") from e


def read_protocols(init_source: str, pkg: str) -> Protocols:
    """The ``Has*`` protocols declared in ``src/<pkg>/nodes/__init__.py``."""
    tree = _parse(init_source, f"src/{pkg}/nodes/__init__.py")
    origins = _origins(tree, f"{pkg}.nodes")
    fields: dict[str, list[tuple[str, str]]] = {}
    imports: dict[str, Imports] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.ClassDef) and stmt.name.startswith("Has"):
            own = [
                (s.target.id, ast.unparse(s.annotation))
                for s in stmt.body
                if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)
            ]
            fields[stmt.name] = own
            used = set[str]().union(
                *(_names(ast.parse(t, mode="eval")) for _, t in own)
            )
            imports[stmt.name] = _imports_for(used, origins)
    return Protocols(fields, imports, origins)


def _dotted(node: ast.expr) -> list[str] | None:
    """``a.b.C`` as ``["a", "b", "C"]``, or ``None`` if ``node`` is not such a path."""
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        head = _dotted(node.value)
        return None if head is None else [*head, node.attr]
    return None


def resolve_type(
    type_text: str, field_name: str, origins: Origins
) -> tuple[str, Imports]:
    """``type_text`` with every ``a.b.Type`` path shortened to ``Type``, as
    ``ast.unparse`` writes it, and the imports it needs in the nodes package.

    ``origins`` are the names the nodes package already binds. A path that starts
    with one of them, such as ``datetime.date`` after ``import datetime``, is
    already usable there and is kept as written.

    Raises:
        ValueError: if ``type_text`` is not an expression, is or contains a quoted
            type, uses a name that is not a builtin, not given by its path and not
            bound in ``origins``, or shortens a path to a name ``origins`` binds to
            something else.
    """
    try:
        tree = ast.parse(type_text, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"`{type_text}` is not a type for `{field_name}`") from e

    literals = {
        id(constant)
        for sub in ast.walk(tree)
        if isinstance(sub, ast.Subscript)
        and (_dotted(sub.value) or [""])[-1] == "Literal"
        for constant in ast.walk(sub.slice)
    }
    for sub in ast.walk(tree):
        if (
            isinstance(sub, ast.Constant)
            and isinstance(sub.value, str)
            and id(sub) not in literals
        ):
            raise ValueError(
                f"`{type_text}` quotes a type: give `--state {field_name}` "
                "the type without quotes, so its path can be imported"
            )

    imports = Imports()

    class Shorten(ast.NodeTransformer):
        def visit_Attribute(self, node: ast.Attribute) -> ast.expr:
            path = _dotted(node)
            if path is None:
                self.generic_visit(node)
                return node
            if path[0] in origins:
                return node
            module, name = ".".join(path[:-1]), path[-1]
            bound = origins.get(name)
            if bound is not None and bound != (module, name):
                raise ValueError(
                    f"`{name}` already means something else in nodes/__init__.py, "
                    f"so `{module}.{name}` cannot be imported there as `{name}`"
                )
            imports.add_from(module, name)
            return ast.copy_location(ast.Name(id=name, ctx=ast.Load()), node)

    shortened = Shorten().visit(tree)
    shortened_names = {name for names in imports.from_.values() for name in names}
    for name in sorted(_names(shortened) - shortened_names - BUILTINS):
        if name not in origins:
            where = "" if name == type_text.strip() else f" in `{type_text}`"
            raise ValueError(
                f"`{name}`{where} is not a builtin and nodes/__init__.py does not "
                f"import it: give its path, as in "
                f"`--state {field_name}:<module>.{name}`"
            )
    imports.update(_imports_for(_names(shortened) - shortened_names, origins))
    return ast.unparse(shortened), imports


def _script_method(
    method: ast.FunctionDef | ast.AsyncFunctionDef, lines: list[str]
) -> str:
    """``method``'s signature as written, with a body that is not yet implemented."""
    first = method.body[0]
    if first.lineno > method.lineno:
        signature = lines[method.lineno - 1 : first.lineno - 1]
    else:
        signature = [lines[method.lineno - 1][: first.col_offset].rstrip()]
    start = method.decorator_list[0].lineno if method.decorator_list else method.lineno
    head = lines[start - 1 : method.lineno - 1] + signature
    indent = len(head[0]) - len(head[0].lstrip())
    text = "\n".join("    " + line[indent:] if line.strip() else "" for line in head)
    return text + '\n        raise NotImplementedError("not yet implemented")'


def read_node(source: str, name: str, cls_name: str, pkg: str) -> NodeInfo:
    """What a walk needs to know about the node ``name`` whose source is ``source``."""
    what = f"src/{pkg}/nodes/{name}.py"
    tree = _parse(source, what)
    classes = {s.name: s for s in tree.body if isinstance(s, ast.ClassDef)}

    node = classes.get(cls_name)
    run = next(
        (
            s
            for s in (node.body if node else [])
            if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))
            and s.name == "run"
        ),
        None,
    )
    if run is None or len(run.args.args) < 2:
        raise SourceError(f"{what} has no class {cls_name} with `run(self, state)`")

    terminal = isinstance(run.returns, ast.Constant) and run.returns.value is None
    outcomes: tuple[str, ...] | None = None
    if not terminal:
        enum = classes.get("Outcome")
        if enum is None:
            raise SourceError(f"{what} has no `Outcome` but `run` does not return None")
        outcomes = tuple(
            t.id
            for s in enum.body
            if isinstance(s, ast.Assign)
            for t in s.targets
            if isinstance(t, ast.Name)
        )

    state = run.args.args[1].annotation
    state_name = state.id if isinstance(state, ast.Name) else None
    if state_name is None:
        raise SourceError(f"{what}: cannot tell which state `run` takes")
    if state_name == "object":
        protocols: tuple[str, ...] = ()
    elif state_name.startswith("Has"):
        protocols = (state_name,)
    elif state_name in classes:
        protocols = tuple(
            b.id
            for b in classes[state_name].bases
            if isinstance(b, ast.Name) and b.id.startswith("Has")
        )
    else:
        raise SourceError(f"{what}: cannot tell which state `run` takes")

    lines = source.splitlines()
    methods = [
        s
        for s in (classes["Utils"].body if "Utils" in classes else [])
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    used = set[str]()
    for method in methods:
        signature = [*method.args.args, *method.args.kwonlyargs]
        for arg in signature:
            if arg.annotation is not None:
                used |= _names(arg.annotation)
        if method.returns is not None:
            used |= _names(method.returns)

    return NodeInfo(
        name=name,
        cls_name=cls_name,
        outcomes=outcomes,
        fallible="Error" in classes,
        protocols=protocols,
        utils=tuple(_script_method(m, lines) for m in methods),
        imports=_imports_for(used, _origins(tree, f"{pkg}.nodes.{name}")),
    )
