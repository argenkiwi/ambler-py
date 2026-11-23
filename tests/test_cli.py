import sys
from unittest.mock import patch

import pytest

from ambler.cli import main


def test_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    with patch.object(sys, "argv", ["ambler-cli", "--help"]):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "node" in captured.out
    assert "walk" in captured.out
    assert "check" in captured.out
