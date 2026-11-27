"""Asks for a number, counts up from it once a second, and stops at random.

See ``../spec.md``. The public surface is ``Error`` and ``run()``; the other
names are exported only for the wiring test.
"""

from dataclasses import dataclass, field
from enum import Enum, auto

from ambler import Walk
from ambler.examples.counter.nodes import count, start
from ambler.examples.counter.nodes.count import Count
from ambler.examples.counter.nodes.start import Start
from ambler.examples.counter.nodes.stop import Stop

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
