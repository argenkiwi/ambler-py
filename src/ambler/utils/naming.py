"""Pure name-case conversions used when scaffolding."""

import re


def to_snake(s: str) -> str:
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return s.replace("-", "_").lower()


def to_pascal(s: str) -> str:
    return "".join(part.capitalize() for part in to_snake(s).split("_") if part)


def to_shout(s: str) -> str:
    return to_snake(s).upper()
