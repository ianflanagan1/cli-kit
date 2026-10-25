import builtins
import os
import pty

import pytest

from cli_kit import terminal
from cli_kit.colour import Style
from cli_kit.outcome import Precondition

UP = b"\x1b[A"
DOWN = b"\x1b[B"
ENTER = b"\n"
OPTIONS = ["local", "pr-rebase", "pr-merge", "skip"]


def no_tty(path, *args, **kwargs):
    raise OSError(6, "Device not configured", path)


def test_fails_when_there_is_no_terminal(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(builtins, "open", no_tty)
    with pytest.raises(Precondition, match="No terminal"):
        terminal.ask("Type it: ")


def test_choosing_with_no_terminal_chooses_nothing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(builtins, "open", no_tty)
    assert terminal.choose("Mode?", OPTIONS) is None


def pick(*keys: bytes) -> tuple[int, str]:
    shown: list[str] = []
    chosen = terminal.pick("Mode?", OPTIONS, iter(keys), shown.append, Style(enabled=False))
    return chosen, "".join(shown)


def test_enter_chooses_the_first_option_at_first():
    assert pick(ENTER)[0] == 0


def test_the_down_arrow_moves_to_the_next_option():
    assert pick(DOWN, DOWN, ENTER)[0] == 2


def test_the_up_arrow_moves_to_the_option_before():
    assert pick(DOWN, DOWN, UP, ENTER)[0] == 1


def test_the_arrows_stop_at_the_first_and_last_options():
    assert pick(UP, ENTER)[0] == 0
    assert pick(DOWN, DOWN, DOWN, DOWN, DOWN, ENTER)[0] == 3


def test_the_arrows_in_application_mode_move_too():
    assert pick(b"\x1bOB", b"\x1bOB", b"\x1bOA", ENTER)[0] == 1


def test_other_keys_are_ignored():
    assert pick(b"x", b"\x1b", DOWN, b"q", ENTER)[0] == 1


def test_carriage_return_chooses_too():
    assert pick(DOWN, b"\r")[0] == 1


def test_the_prompt_and_options_are_shown_with_a_marker_on_the_current_one():
    shown = pick(ENTER)[1]
    assert shown.startswith("Mode?\n")
    assert "❯ local" in shown
    assert "  pr-rebase" in shown


def test_once_chosen_the_options_give_way_to_the_prompt_and_the_choice():
    shown = pick(DOWN, ENTER)[1]
    assert shown.endswith("Mode? pr-rebase\n")


def test_keys_ending_before_a_choice_is_made_choose_nothing():
    shown: list[str] = []
    keys = iter([DOWN])
    assert terminal.pick("Mode?", OPTIONS, keys, shown.append, Style(enabled=False)) is None


def test_a_real_terminal_is_read_a_key_at_a_time(monkeypatch: pytest.MonkeyPatch):
    controller, device = pty.openpty()
    path = os.ttyname(device)
    real_open = builtins.open

    def the_pty(file, *args, **kwargs):
        return real_open(path if file == "/dev/tty" else file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", the_pty)
    os.write(controller, DOWN + DOWN + ENTER)
    try:
        assert terminal.choose("Mode?", OPTIONS) == 2
    finally:
        os.close(controller)
        os.close(device)
