---
name: ambler-util
description: Creates or extracts utility modules into the src/ambler/utils/ directory of an Ambler Python project. Use this whenever a node's SystemUtils needs third-party packages, contains logic reusable across multiple nodes, or has implementations too complex to inline — even if the user just says "add a util", "extract this helper", "share this function", "create a utility", or "this code is getting too long for the node". When a user creates a node that pulls in a new package or has complex async logic, proactively suggest using this skill.
metadata:
  author: leandro
  version: "3.0-python"
---

# Ambler Util (Python)

Follow these steps to create or extract a utility module in the `src/ambler/utils/` directory.

## When to create a utility

Create a `src/ambler/utils/<name>.py` file when a node's `SystemUtils` contains:

1. **Third-party dependencies** — any package not already in `pyproject.toml` (e.g., `httpx`, `pyyaml`)
2. **Reusable logic** — code that is or could be used by more than one node
3. **Complex implementations** — functions with significant logic (error handling, retries, client caching, multi-step operations) that clutter the node file

Simple one-liners like `print(message)` or `random.random() < p` belong in `SystemUtils` directly — no need to extract them.

---

## 1. Gather requirements

Before writing, determine:

- **Utility name**: What capability does this module provide? (e.g., `ollama_chat`, `file_writer`, `markdown_parser`). File will be named `src/ambler/utils/<name>.py` (`snake_case`).
- **Functions to export**: What are the signatures? What arguments and return types?
- **Dependencies**: Does it require extra packages? Which ones?
- **Nodes that will use it**: Which node(s) will call this utility from their `SystemUtils`?

If any of the above is unclear, ask the user before writing code.

---

## 2. Create `src/ambler/utils/<name>.py`

Export functions that implement the side-effectful work. Keep the module focused on a single capability.

```python
"""Append-only journal file."""

import asyncio
from pathlib import Path

JOURNAL_PATH = Path("journal.log")
"""File that journal entries are appended to."""

# Stateful resources live here and stay private to the module.
_write_lock = asyncio.Lock()


async def append(entry: str) -> None:
    """Appends ``entry`` as a new line to the journal file, creating it if needed.

    Raises:
        OSError: if the file could not be opened or written.
    """
    async with _write_lock:
        await asyncio.to_thread(_write_line, entry)


def _write_line(entry: str) -> None:
    with JOURNAL_PATH.open("a", encoding="utf-8") as f:
        f.write(f"{entry}\n")
```

See `src/ambler/examples/counter/terminal.py` for an existing utility used by `src/ambler/examples/counter/start.py`.

### Rules

- **Export only functions** — never export clients, connections or module-level state. Callers interact through function calls with clear signatures. Keep private helpers `_underscored`.
- **Keep state private** — if the utility needs to cache a client or serialise access, use a private module-level variable (`_client`, `_lock`) or `functools.cache`, never a public one.
- **Match the node's `Utils` protocol** — return the same type the consuming node's `Utils` method declares, so `SystemUtils` is a one-line delegation.
- **Raise on failure, don't return `False` or `None`** — the node decides whether a failure is an `Outcome` or an `Error`. Never hide it. Document what is raised.
- **Don't block the event loop** — async utils use async libraries, or push blocking calls into `asyncio.to_thread`.
- **No Ambler imports** — utility modules must not import from `ambler`, `ambler.nodes` or `ambler.walks`. They are plain Python helpers.
- **Extract URL and config constants** — don't inline magic strings like API base URLs or file paths. Pull them into named `UPPER_CASE` constants at the top of the module so they're easy to find and change.
- **Type everything** — `uv run pyright` runs in strict mode.

### Docstrings

Every exported function gets a docstring. This helps both humans reading the code and agents using the utility in future nodes understand what it does without having to trace the implementation.

```python
async def fetch_weather(city: str, api_key: str) -> float:
    """Fetches the current temperature for a city from the OpenWeather API.

    Returns the temperature in Celsius.

    Raises:
        httpx.HTTPError: if the request fails.
        ValueError: if the response is not understood.
    """
```

Keep it brief — a one-sentence summary, then a line on what it returns. Fallible functions get a `Raises:` section.

---

## 3. Update `pyproject.toml` (if using extra packages)

If the utility needs a package that isn't already a dependency, add it with uv:

```bash
uv add httpx
```

This updates `[project] dependencies` in `pyproject.toml` and `uv.lock`. Check `pyproject.toml` first — the package may already be listed. The template has no runtime dependencies by default; dev tools (`pytest`, `pytest-asyncio`, `pyright`, `ruff`) live in the `dev` dependency group (`uv add --dev <pkg>`).

---

## 4. Connect to the node

Import the utility in the node module and use it in `SystemUtils`. The `Utils` protocol stays unchanged — only the implementation on `SystemUtils` changes.

```python
from ambler.utils import journal


class Utils(Protocol):
    async def log(self, entry: str) -> None: ...


class SystemUtils:
    async def log(self, entry: str) -> None:
        await journal.append(entry)
```

Tests still inject a `MockUtils` and never touch the utility — that's the point of the `Utils` protocol.

---

## 5. Checklist before finishing

- [ ] `src/ambler/utils/<name>.py` exists and exports the required functions.
- [ ] All extra packages are listed in `pyproject.toml` (via `uv add`).
- [ ] Exported function return types match the node's `Utils` methods.
- [ ] Fallible functions raise (and document it), and async functions don't block the event loop.
- [ ] Stateful resources (clients, caches, locks) are private module-level names.
- [ ] URL/config constants are extracted to named `UPPER_CASE` constants.
- [ ] Every exported function has a docstring (with `Raises:` if fallible).
- [ ] The node's `SystemUtils` delegates to the utility function.
- [ ] No `ambler`, `ambler.nodes` or `ambler.walks` imports appear in the utility module.
- [ ] Node tests still use fake utils — they need no changes (`uv run pytest`).
