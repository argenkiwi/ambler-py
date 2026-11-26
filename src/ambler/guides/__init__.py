"""The guides ``uv run ambler help [topic]`` prints.

They ship as package data with the CLI that enforces them, so a project reads the
guides of the version it pins.
"""

from importlib.resources import files

TOPICS = (
    "node",
    "util",
    "walk",
    "check",
    "conventions",
    "node-design",
    "testing",
    "spec",
)


def guide(topic: str | None = None) -> str | None:
    """The guide for ``topic``, the general guide for none, or ``None`` if unknown."""
    name = topic or "general"
    if topic and topic not in TOPICS:
        return None
    return (files(__package__) / f"{name}.md").read_text(encoding="utf-8")
