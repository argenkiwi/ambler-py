---
name: ambler-test
description: Adds or updates tests for an existing Ambler node that already has an implementation. Use this when a node exists in src/ambler/nodes/<name>.py but has no tests/nodes/test_<name>.py, when tests need extending after new branches were added, or when retrofitting TDD onto existing code. For creating a brand-new node with tests, use `/ambler-node` instead.
metadata:
  author: leandro
  version: "3.0-python"
---

# Ambler Test (Python)

Follow these steps to add or update tests for an existing node in `src/ambler/nodes/`.

> For brand-new nodes, use `/ambler-node` — it creates both the implementation and tests via a TDD cycle. This skill is for retrofitting tests onto nodes that already exist.

---

## 1. Read the existing node

Read `src/ambler/nodes/<name>.py` in full. Identify:

- **State protocol** (the type of `run`'s `state` parameter, e.g. `HasCount` — defined in `src/ambler/nodes/__init__.py`), the **`Outcome`** members, the **`Error`** exception, and the **`Utils`** protocol methods.
- **Async utils**: Are any util methods `async def`? Those are faked with `async def` too.
- **All branches**: Every place the node returns an `Outcome` member or raises is one branch. List them all — each becomes a test.

---

## 2. Check for existing tests

Check whether `tests/nodes/test_<name>.py` exists.

- If it **does not exist**: write a complete new test module covering every branch.
- If it **does exist**: read it, identify which branches already have coverage, and list the gaps. Only add tests for uncovered branches — do not overwrite passing tests unless the node's interface changed.

---

## 3. Write or update `tests/nodes/test_<name>.py`

One async test per uncovered branch. All utils must be faked.

```python
from dataclasses import dataclass

import pytest

from ambler.nodes.start import Error, Outcome, Start


@dataclass
class MockState:
    count: int


@dataclass
class MockUtils:
    input: str | OSError | None

    # Each util is deterministic and side-effect-free.
    def read_line(self, message: str) -> str | None:
        if isinstance(self.input, OSError):
            raise self.input
        return self.input

    def print(self, message: str) -> None:
        pass


async def run(input: str | None, count: int) -> tuple[Outcome, int]:
    state = MockState(count)
    outcome = await Start(MockUtils(input)).run(state)
    return outcome, state.count


async def test_succeeds_with_input_number() -> None:
    assert await run("42", 0) == (Outcome.SUCCESS, 42)


async def test_reports_invalid_input_and_keeps_count() -> None:
    assert await run("abc", 123) == (Outcome.INVALID_INPUT, 123)


async def test_fails_if_input_cannot_be_read() -> None:
    state = MockState(1)

    with pytest.raises(Error):
        await Start(MockUtils(BrokenPipeError())).run(state)

    assert state.count == 1
```

For **async utils**, fake them with an `async def` that returns immediately:

```python
@dataclass
class MockUtils:
    heads: bool

    def print(self, message: str) -> None:
        pass

    async def sleep(self, seconds: float) -> None:
        pass

    def random_bool(self, p: float) -> bool:
        return self.heads
```

To assert on what a util received, record it on the fake (e.g. a `printed: list[str]` field) and check it after the run (see `tests/nodes/test_stop.py`).

### Test rules

- **One test per branch** — cover every `Outcome` member and every error the node can raise.
- **Fake all `Utils`** — a `MockUtils` class with no real I/O, network, or timing. Prefer small classes over `unittest.mock` so pyright checks them against the protocol.
- **Fake the state** — a `MockState` dataclass with only the attributes the node requires.
- **Assert the `Outcome` member and the state** — nodes do not know node ids.
- **Test names**: `test_<expected_behaviour>_<condition>` (e.g., `test_reports_invalid_input_and_keeps_count`).
- **Always `async def` and `await`** — `run` is a coroutine, even for synchronous nodes.

---

## 4. Run tests — must pass

```bash
uv run pytest tests/nodes/test_<name>.py
uv run pyright
```

All tests must pass. If any fail, fix the implementation (not the tests).

---

## 5. Checklist before finishing

- [ ] `tests/nodes/test_<name>.py` exists.
- [ ] It has one async test per branch.
- [ ] `MockState` and `MockUtils` are defined — no real I/O, network, or timing.
- [ ] Every outcome and error path has a dedicated test.
- [ ] Test names follow `test_<expected_behaviour>_<condition>`.
- [ ] All tests pass (`uv run pytest`) and `uv run pyright` is clean.
