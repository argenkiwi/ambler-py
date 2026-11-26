# uv run ambler

Scaffolds and checks a Python Ambler project (on uv): a program built as walks (state machines) of small, tested nodes. It is the project's own CLI, a dev dependency, so it needs nothing installed beyond `uv sync`.

    uv run ambler node <name> …                  add a node: its contract, a raising `run`, failing tests
    uv run ambler util <name>                    add a module of side-effectful functions
    uv run ambler walk <name> --nodes … --edge … wire nodes into a walk, with its test, spec and script
    uv run ambler check [--lint-only]            verify the conventions, then ruff, pyright and pytest
    uv run ambler help [topic]                   this guide, or one topic

Topics: a verb (node, util, walk, check), or conventions, node-design, testing, spec.

Exit codes: 0 success, 1 a check failed or the thing to create already exists, 2 invalid arguments or an unexpected error.

Where the `ambler` command is installed, `ambler <verb>` runs the same thing. It also creates projects (`ambler new`) and implements a spec with an agent loop (`ambler pave`); neither is needed to work inside a project.

## The four ideas

- State: one dataclass per walk. Nodes ask for state through small protocols, `HasCount`, kept in `nodes/__init__.py`; the walk's `State` has every field they need, which pyright checks.
- Node: one step. A frozen dataclass whose `async def run(self, state)` mutates the state and returns a member of its `Outcome` enum: what happened, never which node comes next.
- Utils: a node's side effects, one method each, in its `Utils` protocol. `SystemUtils` is the real thing; tests pass their own.
- Walk: a `Walk[Id, State]` subclass whose `step` matches each node's outcomes to the next `Id`. The match has no `case _:`, so pyright fails on an unwired outcome.

## Layout

    src/<package>/engine.py     Node and Walk (identical in every project)
    src/<package>/walks/        one module per walk; each has a `main()` run by a pyproject.toml script
    src/<package>/nodes/        one module per node; the state protocols in __init__.py
    src/<package>/utils/        side-effectful functions nodes delegate to
    tests/nodes/  tests/walks/  one test module per node and per walk
    specs/                      one plain-language spec per walk

## Usual order of work

1. Describe the walk in `specs/<walk>.md` (`uv run ambler help spec`).
2. For each node: `uv run ambler node`, then tests, then the body (`uv run ambler help node-design`, `uv run ambler help testing`).
3. `uv run ambler walk` to wire them; finish the wiring test (`uv run ambler help walk`).
4. `uv run ambler check`.

Run `uv sync` once in a new project, so this CLI, the checks and the formatter are there.
