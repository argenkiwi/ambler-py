import subprocess
import sys
from unittest.mock import patch

import pytest

from ambler.cli import main


def run_main(*argv: str) -> int:
    with (
        patch.object(sys, "argv", ["ambler-cli", *argv]),
        pytest.raises(SystemExit) as exc,
    ):
        main()
    assert isinstance(exc.value.code, int)
    return exc.value.code


def test_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_main("--help") == 0
    out = capsys.readouterr().out
    assert "node" in out
    assert "walk" in out
    assert "check" in out


def test_cli_exits_with_the_walks_exit_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_main("bogus") == 2
    assert "Unknown command: bogus" in capsys.readouterr().err


def test_cli_runs_as_a_module() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "ambler.cli", "bogus"], capture_output=True, text=True
    )
    assert proc.returncode == 2
    assert "Unknown command: bogus" in proc.stderr
