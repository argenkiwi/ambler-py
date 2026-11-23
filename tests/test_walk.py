from enum import Enum, auto

import pytest

from ambler import Walk


class Id(Enum):
    A = auto()
    B = auto()
    C = auto()


class Scripted(Walk[Id, list[str]]):
    """Records each id it visits, follows A -> B -> C and halts; fails at C if asked."""

    def __init__(self, *, fail_at_c: bool = False) -> None:
        self.fail_at_c = fail_at_c

    async def step(self, id: Id, state: list[str]) -> Id | None:
        if id is Id.C and self.fail_at_c:
            raise RuntimeError("boom")
        state.append(id.name)
        match id:
            case Id.A:
                return Id.B
            case Id.B:
                return Id.C
            case Id.C:
                return None


async def test_run_steps_until_a_node_halts() -> None:
    visited: list[str] = []

    await Scripted().run(Id.A, visited)

    assert visited == ["A", "B", "C"]


async def test_run_starts_wherever_it_is_told() -> None:
    visited: list[str] = []

    await Scripted().run(Id.B, visited)

    assert visited == ["B", "C"]


async def test_run_stops_at_the_first_error() -> None:
    visited: list[str] = []

    with pytest.raises(RuntimeError, match="boom"):
        await Scripted(fail_at_c=True).run(Id.A, visited)

    assert visited == ["A", "B"]
