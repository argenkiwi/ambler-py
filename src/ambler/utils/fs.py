"""File-system and output capabilities shared by the scaffolding nodes."""

import re
import sys
from pathlib import Path
from typing import Protocol

from ambler.utils.naming import to_snake


class ProjectError(Exception):
    """The current folder is not a Python project the scaffolders understand."""


class ScaffoldUtils(Protocol):
    def root(self) -> Path:
        """The project root: the current folder."""
        ...

    def package_name(self) -> str:
        """The importable package under ``src/``.

        Raises:
            ProjectError: if there is no ``pyproject.toml`` in the project root.
        """
        ...

    def exists(self, path: Path) -> bool: ...

    def mkdir(self, path: Path) -> None: ...

    def read_text(self, path: Path) -> str: ...

    def write_text(self, path: Path, content: str) -> None: ...

    def print(self, message: str) -> None: ...

    def print_error(self, message: str) -> None: ...


class SystemScaffoldUtils:
    def root(self) -> Path:
        return Path.cwd()

    def package_name(self) -> str:
        root = self.root()
        pyproject = root / "pyproject.toml"
        if not pyproject.exists():
            raise ProjectError("No pyproject.toml found in current folder.")

        src = root / "src"
        if src.exists():
            candidates = [
                d for d in src.iterdir() if d.is_dir() and (d / "__init__.py").exists()
            ]
            if candidates:
                return candidates[0].name

        match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', pyproject.read_text())
        return to_snake(match.group(1) if match else "ambler")

    def exists(self, path: Path) -> bool:
        return path.exists()

    def mkdir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def read_text(self, path: Path) -> str:
        return path.read_text()

    def write_text(self, path: Path, content: str) -> None:
        path.write_text(content)

    def print(self, message: str) -> None:
        print(message)

    def print_error(self, message: str) -> None:
        print(message, file=sys.stderr)
