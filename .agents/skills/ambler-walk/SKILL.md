---
name: ambler-walk
description: Creates a complete Ambler walk — the Python module that wires the nodes (src/ambler/walks/<name>.py), its wiring test (tests/walks/test_<name>.py), the Markdown spec (specs/<name>.md) and the entry point that runs it — and ensures all required nodes exist. Use this whenever a user wants to add a new program or flow to an Ambler Python project, even if they say "new walk", "add a program", "wire up these nodes", or just describe what they want the app to do.
metadata:
  author: leandro
  version: "3.0-python"
---

# Ambler Walk (Python)

This skill guides you in creating a complete Ambler walk. A walk is a state-machine graph consisting of:

1. `src/ambler/walks/<name>.py` — Python module defining the shared `State`, the `Id` enum, a `Walk` subclass owning the nodes and wiring each node's outcomes to successors, and `run()`. Its public surface (`__all__`) is only `Error` and `run`.
2. `tests/walks/test_<name>.py` — the wiring test.
3. `specs/<name>.md` — Markdown specification describing the shared state and the logic/transitions of each step.
4. An entry point — `src/ambler/__main__.py` if this is the branch's primary program, otherwise a `[project.scripts]` entry — that runs `ambler.walks.<name>.run()`.

---

## Step 1 — Identify the Walk

- Determine the walk name (lowercase `snake_case`, e.g. `my_walk`). The file will be `src/ambler/walks/<name>.py`.
- Clarify the walk's purpose: what program does it implement?
- Identify the nodes (steps) required and their transitions.

---

## Step 2 — Research and Reuse

Before creating new nodes, research existing ones to promote reuse and consistency:

- **Review Existing Specs:** Browse `specs/*.md` to identify nodes that already implement the required logic (e.g., "Ollama Check", "Model Select"). This is more efficient than reading source code and helps maintain architectural alignment.
- **Check Node Implementation:** For each node identified, verify it exists in `src/ambler/nodes/<node_name>.py`. Note which state protocol each node's `run` takes (e.g., `HasCount`) — the walk's `State` must satisfy all of them — and each node's `Outcome` members and `Error`, since the walk must handle every one.

---

## Step 3 — Create the Specification File (`specs/<name>.md`)

Create the Markdown spec using the `/ambler-spec` skill. This acts as the **blueprint** for the entire walk, defining the shared state and the logic for every node.

---

## Step 4 — Ensure Nodes Exist

For each node defined in the specification:

- If it does **not** exist in `src/ambler/nodes/<node_name>.py`, create it using the `/ambler-node` skill. This runs a full TDD pass — skeleton, tests (red), implementation, tests (green) — before completing. No separate test step is needed.
- If the node already exists but has no `tests/nodes/test_<node_name>.py`, use the `/ambler-test` skill to retrofit coverage.

---

## Step 5 — Create the Walk Module (`src/ambler/walks/<name>.py`)

Example: `src/ambler/walks/counter.py`.

```python
"""Asks for a number, counts up from it once a second, and stops at random.

See ``specs/counter.md``.
"""

from dataclasses import dataclass, field
from enum import Enum, auto

from ambler import Walk
from ambler.nodes import count, start
from ambler.nodes.count import Count
from ambler.nodes.start import Start
from ambler.nodes.stop import Stop

__all__ = ["Error", "run"]

Error = start.Error
"""What can stop the walk early. Only the start node can fail."""


@dataclass
class State:
    count: int = 0


class Id(Enum):
    START = auto()
    COUNT = auto()
    STOP = auto()


@dataclass(frozen=True)
class Counter(Walk[Id, State]):
    start: Start = field(default_factory=Start)
    count: Count = field(default_factory=Count)
    stop: Stop = field(default_factory=Stop)

    async def step(self, id: Id, state: State) -> Id | None:
        match id:
            case Id.START:
                match await self.start.run(state):
                    case start.Outcome.SUCCESS:
                        return Id.COUNT
                    case start.Outcome.INVALID_INPUT:
                        return Id.START
            case Id.COUNT:
                match await self.count.run(state):
                    case count.Outcome.AGAIN:
                        return Id.COUNT
                    case count.Outcome.FINISHED:
                        return Id.STOP
            case Id.STOP:
                await self.stop.run(state)
                return None


async def run() -> None:
    """Runs the counter walk starting at 0.

    Raises:
        Error: if reading user input fails.
    """
    await Counter().run(Id.START, State())
```

**Key rules:**
- Import `Walk` from `ambler`, each node module (for its `Outcome`) and node class from `ambler.nodes`.
- `__all__ = ["Error", "run"]` declares the public surface. `State`, `Id` and the walk class are importable only so the wiring test can build the walk with fakes; runners never touch them.
- Define `State` as a dataclass that satisfies every state protocol required by the walk's nodes. Give fields defaults when the walk starts from an empty state.
- Define an `Id` enum with one `UPPER_SNAKE_CASE` member per node, spelled exactly like the spec's backtick references.
- Define a frozen dataclass subclassing `Walk[Id, State]` with one field per node, each defaulting to the production node (`field(default_factory=Start)`). `Counter()` gives production wiring; tests pass nodes built with fakes.
- `step` matches on `Id` and, for each node, matches on its `Outcome`, returning the next `Id` or `None` to halt. **Do not add a `case _:` arm**: pyright's `reportMatchNotExhaustive` (enabled in `pyproject.toml`) then fails on any new outcome or id until it is wired. Without that check a missing case would fall through and silently halt, so `uv run pyright` is part of the build.
- Choose `Error` to fit the nodes: alias a node's own exception if only one node can fail (`Error = start.Error`), or define a walk-level `class Error(Exception)` and have the nodes' errors subclass it, or translate them in `step` with `raise Error(...) from e`. Runners catch only `ambler.walks.<name>.Error`, never a node's error.
- Terminal nodes return `None` from `run`; `step` returns `None` after them.
- `Walk.run(start_id, state)` runs the loop; do not hand-write one.
- `run()` builds the initial state. If the walk needs command-line arguments, parse them in the entry point with `argparse` and pass them to `run()`; users pass them with `uv run <script> <arg1> <arg2>`.

---

## Step 6 — Test the Wiring (`tests/walks/test_<name>.py`)

Build the walk with a single scripted fake that satisfies every node's `Utils` protocol, and assert on the final state and what was printed. Cover each branch of the graph (e.g. an invalid input that loops back to `START`). See `tests/walks/test_counter.py`:

```python
class Script:
    """Plays back typed lines and coin flips, and records everything printed."""

    def __init__(self, lines: Iterable[str], flips: Iterable[bool]) -> None:
        self.lines = deque(lines)
        self.flips = deque(flips)
        self.printed: list[str] = []

    def read_line(self, message: str) -> str | None:
        return self.lines.popleft() if self.lines else None

    def print(self, message: str) -> None:
        self.printed.append(message)

    async def sleep(self, seconds: float) -> None:
        pass

    def random_bool(self, p: float) -> bool:
        return self.flips.popleft()


async def test_retries_invalid_input_then_counts_until_the_coin_says_stop() -> None:
    script = Script(["abc", "3"], [True, False])
    state = State(count=99)

    walk = Counter(start=Start(script), count=Count(script), stop=Stop(script))
    await walk.run(Id.START, state)

    assert state.count == 5
    assert script.printed == [
        "Error: Invalid input. Please enter a number.",
        "Current count: 3",
        "Current count: 4",
        "Final count: 5",
    ]
```

---

## Step 7 — Add the Entry Point and Dependencies

Each branch of this template is one program, so `src/ambler/__main__.py` runs its primary walk. Point it at the new walk:

```python
import asyncio
import sys

from ambler.walks import <name>


def main() -> None:
    try:
        asyncio.run(<name>.run())
    except <name>.Error as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()
```

If the branch already has a primary walk and this one is secondary, put the same code in `src/ambler/walks/<name>.py` as a `main()` function (or a separate `src/ambler/<name>_cli.py`) and register it in `pyproject.toml`:

```toml
[project.scripts]
<primary> = "ambler.__main__:main"   # never `ambler`: that name belongs to the orchestrator CLI
<name> = "ambler.walks.<name>:main"
```

Only touch dependencies if the walk itself (not its nodes or utils) needs a new package — add it with `uv add <package>`. Node and util dependencies are handled by `/ambler-node` and `/ambler-util`.

---

## Step 8 — Verify

Run the walk to confirm it behaves as specified:

```bash
uv run <primary>    # primary walk (src/ambler/__main__.py)
uv run <name>    # secondary walk ([project.scripts] entry)
```

Then run tests, type check and lints:

```bash
uv run pytest
uv run pyright
uv run ruff check && uv run ruff format --check
```

---

## Checklist

Before finishing, confirm:

- [ ] `specs/<name>.md` exists and matches the `Id` members in the walk.
- [ ] `src/ambler/walks/<name>.py` exists with `State`, `Id`, the `Walk` subclass owning the nodes, `run()`, and `__all__ = ["Error", "run"]`.
- [ ] `State` satisfies every state protocol the walk's nodes require.
- [ ] Every node used in the walk has a `src/ambler/nodes/<node_name>.py` with passing tests.
- [ ] Every `Outcome` member of every node is matched explicitly, with no `case _:` arm, and every `Id` has a case.
- [ ] `tests/walks/test_<name>.py` covers each branch of the graph.
- [ ] The entry point calls `ambler.walks.<name>.run()` and catches only `ambler.walks.<name>.Error`.
- [ ] `uv run pytest`, `uv run pyright` and `uv run ruff check` are all clean.
- [ ] The walk runs end-to-end without errors (`uv run <primary>` or `uv run <name>`).
