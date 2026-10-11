import builtins

import pytest

from cli_kit import terminal
from cli_kit.errors import Precondition


def test_fails_when_there_is_no_terminal(monkeypatch: pytest.MonkeyPatch):
    def no_tty(path, *args, **kwargs):
        raise OSError(6, "Device not configured", path)

    monkeypatch.setattr(builtins, "open", no_tty)
    with pytest.raises(Precondition, match="No terminal"):
        terminal.ask("Type it: ")
