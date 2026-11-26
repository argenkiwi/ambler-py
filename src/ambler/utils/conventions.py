"""The structural conventions ``check`` verifies before running the tools.

Pure functions over source text: each returns ``<path>:<line>: <rule>: <what to do>``
lines, one per violation.
"""

import ast

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
