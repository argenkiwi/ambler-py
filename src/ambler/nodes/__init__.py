"""Reusable atomic step nodes and the shared state protocols they require."""

from typing import Protocol


class HasArgv(Protocol):
    """A state that has an argv field."""

    argv: list[str]


class HasCommand(Protocol):
    """A state that has a command field."""

    command: str | None


class HasExitCode(Protocol):
    """A state that has an exit_code field."""

    exit_code: int
