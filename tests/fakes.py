from pathlib import Path

from ambler.utils.fs import ProjectError

ROOT = Path("/proj")


class FakeFs:
    """In-memory ``ScaffoldUtils`` that records files and output."""

    def __init__(
        self, files: dict[Path, str] | None = None, package: str | None = "demo"
    ) -> None:
        self.files = dict(files or {})
        self.package = package
        self.out: list[str] = []
        self.errors: list[str] = []
        self.formatted: list[Path] = []

    def root(self) -> Path:
        return ROOT

    def package_name(self) -> str:
        if self.package is None:
            raise ProjectError("No pyproject.toml found in current folder.")
        return self.package

    def exists(self, path: Path) -> bool:
        return path in self.files

    def mkdir(self, path: Path) -> None:
        pass

    def read_text(self, path: Path) -> str:
        return self.files[path]

    def write_text(self, path: Path, content: str) -> None:
        self.files[path] = content

    def print(self, message: str) -> None:
        self.out.append(message)

    def print_error(self, message: str) -> None:
        self.errors.append(message)

    def format(self, paths: list[Path]) -> None:
        self.formatted.extend(paths)
