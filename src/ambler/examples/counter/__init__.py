"""Example walk: asks for a number, counts up from it, and stops at random.

See ``spec.md``. Run with ``uv run ambler-counter``.
"""

from typing import Protocol


class HasCount(Protocol):
    """A state that has a count field."""

    count: int
