# ambler

A predictable architecture for writing programs as graphs, in Python.

A program is a set of small **nodes** joined into a **walk**. Each node does one thing to shared state and reports what happened. The walk decides where to go next. The wiring is a `match` with no wildcard arm, checked by pyright in strict mode, so a missing edge is a type error rather than a runtime surprise.

> [!NOTE]
> This is a port of [ambler-rs](https://github.com/argenkiwi/ambler-rs), reworked to use Python idioms: protocols, exceptions, dataclasses and `asyncio`. It does not mirror the Rust API.

## Quick start

Requires [uv](https://docs.astral.sh/uv/). uv fetches a suitable Python (3.12 or later) if you don't have one.

```bash
uv run ambler
```

The program asks for a starting number, counts up once a second, and stops at random. Invalid input sends the walk back to the start. See [`specs/counter.md`](specs/counter.md) for the behaviour it implements.

## Concepts

| Concept | Python | Role |
|---|---|---|
| State | Your own dataclass, plus small protocols such as `HasCount` | Shared data that every node reads and mutates in place. |
| Node | `Node[S, O]` protocol | One step. `async def run(self, state)` returns a member of the node's `Outcome` enum (one member per outgoing edge), or raises the node's `Error`. |
| Utils | A per-node `Utils` protocol | Every side effect (printing, stdin, sleeping, randomness) so tests can swap in fakes. |
| Walk | `Walk[Id, S]` base class | Owns the nodes, matches each outcome to the next `Id` (or `None` to halt), and runs the loop. |

Nodes never name their successors, so the same node can be reused in any walk.

## Writing a node

A node is a frozen dataclass whose `utils` default to the real ones:

```python
@dataclass(frozen=True)
class Count:
    utils: Utils = field(default_factory=SystemUtils)

    async def run(self, state: HasCount) -> Outcome:  # AGAIN | FINISHED
        self.utils.print(f"Current count: {state.count}")
        await self.utils.sleep(1)
        state.count += 1

        return Outcome.AGAIN if self.utils.random_bool(0.5) else Outcome.FINISHED
```

`Count()` uses `SystemUtils`; `Count(fake)` is for tests. The full node is in [`src/ambler/nodes/count.py`](src/ambler/nodes/count.py).

## Writing a walk

A walk owns its nodes and wires every outcome:

```python
async def step(self, id: Id, state: State) -> Id | None:
    match id:
        case Id.START:
            match await self.start.run(state):
                case start.Outcome.SUCCESS:
                    return Id.COUNT
                case start.Outcome.INVALID_INPUT:
                    return Id.START
        # ...
```

Then `await walk.run(Id.START, state)` steps until a node halts. The complete walk is in [`src/ambler/walks/counter.py`](src/ambler/walks/counter.py), its wiring test is in [`tests/walks/test_counter.py`](tests/walks/test_counter.py), and [`src/ambler/__main__.py`](src/ambler/__main__.py) runs it.

> [!TIP]
> Don't add a `case _:` arm when matching outcomes. Leaving it out is what makes pyright (`reportMatchNotExhaustive`, enabled in `pyproject.toml`) fail on a newly added outcome until it is wired. Treat `uv run pyright` as part of the build: a walk that skips the check silently halts on an unwired outcome.

## Project layout

```text
src/ambler/__init__.py   Node protocol and Walk base class
src/ambler/__main__.py   The program: runs this branch's primary walk
src/ambler/walks/        Walks wiring nodes together
src/ambler/nodes/        Reusable atomic step nodes and shared state protocols
src/ambler/utils/        Side-effectful utilities (terminal I/O, external APIs, system services)
tests/                   pytest suite, mirroring src/ambler/
specs/                   Plain-language spec for each walk
notes/                   Design notes (Zettelkasten, Markdown source of truth)
.agents/skills/          Agent skills for creating nodes, utils, tests, walks and specs
```

## Development

```bash
uv run pytest                     # node and walk tests
uv run pyright                    # strict type check, including match exhaustiveness
uv run ruff check
uv run ruff format --check
```

Nodes are built test-first: every outcome and error gets one async pytest test, with all utils faked.

The [`.agents/skills`](.agents/skills) directory holds step-by-step guides for coding agents:

| Skill | Use it to |
|---|---|
| `ambler-node` | Add a node using TDD |
| `ambler-test` | Add tests to an existing node |
| `ambler-util` | Extract a reusable helper into `src/ambler/utils/` |
| `ambler-walk` | Wire nodes into a new walk and spec |
| `ambler-spec` | Write a walk's Markdown spec |

## Projects built with ambler

- [azk](https://github.com/argenkiwi/azk): a CLI for agents to follow the Zettelkasten note-taking methodology.
- [PiDE](https://github.com/argenkiwi/pide): a containerised Pi coding agent backed by a local LLM.
