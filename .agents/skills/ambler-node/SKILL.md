---
name: ambler-node
description: Creates a new Ambler node in src/ambler/nodes/ — with pytest tests in tests/nodes/, using test-driven development. Use this whenever the user wants to add a node, step, or state to an Ambler Python project — even if they phrase it as "add a step", "create a handler", or describe the behaviour without using the word "node". Also use when creating a node WITH tests or following TDD for a new node. For adding tests to an existing node that already has an implementation, use `/ambler-test` instead.
metadata:
  author: leandro
  version: "3.0-python"
---

# Ambler Node (Python)

Follow these steps to create a new node using test-driven development. Tests are written before the implementation.

A node is a frozen dataclass with an `async def run(self, state)` method. It mutates the shared state in place and returns a member of its `Outcome` enum saying what happened. It never names the node that comes next — the walk wires each outcome to a successor (see `/ambler-walk`). Every node module exports the same names: `Outcome`, `Utils`, `SystemUtils` and the node class itself (named after the module, e.g. `Count`), plus an `Error` exception if the node can fail.

It satisfies this protocol from `src/ambler/__init__.py` structurally — nodes do not subclass it:

```python
class Node[S, O](Protocol):
    async def run(self, state: S, /) -> O: ...
```

## 1. Gather requirements

Before writing any code, determine:

- **Research Existing Nodes:** Check `specs/*.md` and `src/ambler/nodes/` to see if a node with similar behaviour already exists. It is always better to reuse or adapt an existing node than to create a duplicate.
- **Node name**: The purpose of the node (e.g., `retry`, `prompt`, `validate`). The file will be named `src/ambler/nodes/<name>.py` (`snake_case`, no `_node` suffix) and the class `<Name>` (`PascalCase`).
- **State shape**: What does this node read or mutate? State is expressed as `Protocol`s with plain attributes (e.g., `class HasCount(Protocol): count: int`). Shared state protocols live in `src/ambler/nodes/__init__.py` — reuse an existing one where possible, otherwise add a new one there. Require only the attributes the node actually touches. Python has no intersection types, so a node needing several protocols declares one combined protocol that inherits from them (`class HasCountAndName(HasCount, HasName, Protocol): ...`).
- **Outcomes**: What distinct results can this node report? Each becomes one member of the `Outcome` enum (`UPPER_SNAKE_CASE`, e.g. `SUCCESS`, `INVALID_INPUT`). A terminal node returns `None` and has no `Outcome`.
- **Errors**: What can go wrong that is not a normal outcome (I/O failure, for example)? The node raises its own `class Error(Exception)`, chaining the cause with `raise Error(...) from e`. A node that cannot fail defines no `Error`.
- **Utils**: What side-effectful operations does the node perform? List them (e.g., `print`, `read_line`, `sleep`, `random_bool`). Each becomes a method on the `Utils` protocol with a production implementation on `SystemUtils`. Prefer domain-level signatures (`sleep(seconds: float)`, `random_bool(p)`) over raw ones (`random() -> float`), and let anything that can fail raise (`OSError` and the like).
- **Behaviour**: What does the node do, and how does it choose which outcome to report?
- **Branches**: List every outcome and error the node can produce. Each becomes one test case. The types and branches decided here are the contract — if you find you need to change them during implementation, restart from this step.

---

## 2. Create a skeleton `src/ambler/nodes/<name>.py`

Add any new state protocol to `src/ambler/nodes/__init__.py` alongside the existing ones:

```python
class HasCount(Protocol):
    """A state that has a count field."""

    count: int
```

Then write only the type exports and a stub `run`. The body must `raise NotImplementedError` so that tests fail in step 4.

```python
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Protocol

from ambler.nodes import HasCount


class Outcome(Enum):
    """Where :class:`<Name>` leaves the walk."""

    SUCCESS = auto()  # from requirements
    FAILURE = auto()


class Utils(Protocol):
    def print(self, message: str) -> None: ...


class SystemUtils:
    def print(self, message: str) -> None:
        print(message)


@dataclass(frozen=True)
class <Name>:
    """One-sentence description of what the node does."""

    utils: Utils = field(default_factory=SystemUtils)

    async def run(self, state: HasCount) -> Outcome:
        raise NotImplementedError
```

`<Name>()` is the production node; tests pass a fake with `<Name>(MockUtils())`.

For a node whose utils are asynchronous, declare them `async def` in both the protocol and `SystemUtils`:

```python
class Utils(Protocol):
    async def sleep(self, seconds: float) -> None: ...


class SystemUtils:
    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
```

For a fallible node, add the exception:

```python
class Error(Exception):
    """The starting number could not be read."""
```

Verify the skeleton type-checks before writing tests:

```bash
uv run pyright src/ambler/nodes/<name>.py
```

---

## 3. Write the tests in `tests/nodes/test_<name>.py`

Write one async test per branch identified in step 1. `asyncio_mode = "auto"` is set in `pyproject.toml`, so plain `async def test_...` functions run without decorators. All utils must be faked — no real I/O, network, or timing.

```python
from dataclasses import dataclass

from ambler.nodes.<name> import <Name>, Outcome


@dataclass
class MockState:
    count: int


class MockUtils:
    def print(self, message: str) -> None:
        pass


async def test_increments_count_and_succeeds() -> None:
    state = MockState(1)

    outcome = await <Name>(MockUtils()).run(state)

    assert outcome is Outcome.SUCCESS
    assert state.count == 2
```

For a fallible node, assert the exception and that the state was left untouched:

```python
    with pytest.raises(Error):
        await Start(MockUtils(BrokenPipeError())).run(state)
    assert state.count == 1
```

**Async utils** are faked with an `async def` that returns immediately:

```python
class MockUtils:
    async def sleep(self, seconds: float) -> None:
        pass
```

To make a fake configurable per test, make it a dataclass with fields (e.g., `MockUtils(heads=True)`). To assert on what a util was called with, record it on the fake and read it back after the run (from `tests/nodes/test_stop.py`):

```python
@dataclass
class MockUtils:
    printed: list[str] = field(default_factory=list[str])

    def print(self, message: str) -> None:
        self.printed.append(message)


# In the test:
utils = MockUtils()
await Stop(utils).run(state)
assert utils.printed == ["Final count: 15"]
```

Write fakes as small classes rather than `unittest.mock.Mock`: pyright checks them against the `Utils` protocol, so a fake that drifts from the protocol fails the type check.

### Test rules

- **One test per branch** — one for each outcome and each error the node can produce.
- **Fake all `Utils`** — a `MockUtils` class satisfying `Utils` deterministically, with no side effects.
- **Fake the state** — a `MockState` dataclass with only the attributes the node requires.
- **Assert the `Outcome` member and the state** — never node ids; nodes do not know them.
- **Test names**: `test_<expected_behaviour>_<condition>` (e.g., `test_reports_invalid_input_and_keeps_count`).
- **Always `async def` and `await`** — `run` is a coroutine, even for synchronous nodes.

---

## 4. Run tests — expect failure

```bash
uv run pytest tests/nodes/test_<name>.py
```

Tests must fail with `NotImplementedError` (or assertion errors). This confirms the tests are actually exercising the code path.

- If tests fail with `NotImplementedError` → correct, proceed to step 5.
- If tests fail with an **import or type error** → the skeleton doesn't match the test — fix the skeleton, not the tests.
- If tests **pass** → the skeleton was too complete; ensure the `run` body only raises `NotImplementedError`.

---

## 5. Implement `src/ambler/nodes/<name>.py`

Replace the stub body with the real logic. The exports (`Outcome`, `Error`, `Utils`, `SystemUtils`, the node class) and the `run` signature stay exactly as written in step 2.

```python
async def run(self, state: HasCount) -> Outcome:
    self.utils.print(f"Current count: {state.count}")
    state.count += 1
    return Outcome.SUCCESS
```

### Key rules

- **State**: Mutate only the `state` you were given — never module-level or global mutable state.
- **Outcomes**: Return an `Outcome` member — never construct or mention a node id inside the node.
- **Errors**: Catch only what you translate. Wrap expected failures in the node's `Error` with `raise Error(...) from e`; do not swallow them with a bare `except` or a default value unless "no value" is a documented outcome.
- **Utils**: All side effects go through `self.utils.*`. Complex or reusable logic (e.g., LLM calls, file I/O, extra packages) should be moved to `src/ambler/utils/` via `/ambler-util`.
- **No blocking calls**: `run` is a coroutine; don't block the event loop. Make slow utils `async`, or wrap blocking work in `asyncio.to_thread` inside `SystemUtils`.
- **Termination**: A terminal node returns `None`; the walk answers it by returning `None` from `step`.
- **Do not modify the tests** between steps 4 and 6 — the tests define the contract; the implementation must satisfy them.

---

## 5a. Adapting Existing Nodes (Optional)

Nodes depend on state protocols, not concrete classes, so reusing an existing node with a walk whose state names the field differently needs no adapter node. Expose the protocol's attribute as a property on the walk's `State`:

```python
@dataclass
class State:
    total: int = 0

    @property
    def count(self) -> int:
        return self.total

    @count.setter
    def count(self, value: int) -> None:
        self.total = value
```

Only write a wrapping node if the existing node's behaviour itself must change, and then treat it as a new node (start again from step 1).

---

## 6. Run tests — must pass

```bash
uv run pytest tests/nodes/test_<name>.py
```

All tests must be green, with `uv run pyright` and `uv run ruff check` clean. Fix the implementation (never the tests) until they pass.

---

## 7. Checklist before finishing

- [ ] `src/ambler/nodes/<name>.py` exists.
- [ ] Any new shared state protocol is defined in `src/ambler/nodes/__init__.py`.
- [ ] `Outcome` has one member per outgoing edge (or the node is terminal and returns `None`).
- [ ] `<Name>` is a frozen dataclass with `utils: Utils = field(default_factory=SystemUtils)` and `async def run(self, state)`.
- [ ] The state protocol requirements are minimal.
- [ ] `SystemUtils` provides real implementations.
- [ ] Only the given `state` is mutated.
- [ ] Failures are raised as the node's `Error`, not swallowed.
- [ ] Shared logic is in `src/ambler/utils/`.
- [ ] `tests/nodes/test_<name>.py` has one async test per branch.
- [ ] All `Utils` in tests are faked.
- [ ] Tests were written (step 3) before the full implementation (step 5).
- [ ] Tests failed on step 4 before passing on step 6.
- [ ] No tests were modified between steps 4 and 6.
