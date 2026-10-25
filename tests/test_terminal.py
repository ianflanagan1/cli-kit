import builtins
import os
import pty
import re

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
    chosen = terminal.pick(
        "Mode?", OPTIONS, iter(keys), shown.append, Style(enabled=False), lambda: 80
    )
    return chosen, "".join(shown)


def rows(shown: str) -> list[str]:
    """Each line drawn, as it looks: the escape codes that move about and style taken out."""
    plain = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", shown)
    return [line.rpartition("\r")[2] for line in plain.split("\n")]


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


def test_once_chosen_the_options_give_way_to_the_prompt_and_the_choice_under_it():
    shown = pick(DOWN, ENTER)[1]
    assert shown.endswith("Mode?\n  ❯ pr-rebase\n")


def test_the_choice_stays_in_sight_however_long_the_prompt_is_cut():
    shown: list[str] = []
    prompt = "How and where does work reach the trunk in a long-named repository?"
    terminal.pick(prompt, LONG, iter([DOWN, ENTER]), shown.append, Style(False), lambda: 30)
    assert rows(shown[-1])[-2:] == ["  ❯ skip", ""]


def test_keys_ending_before_a_choice_is_made_choose_nothing():
    shown: list[str] = []
    keys = iter([DOWN])
    chosen = terminal.pick("Mode?", OPTIONS, keys, shown.append, Style(enabled=False), lambda: 80)
    assert chosen is None


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


LONG = ["local      landed on the trunk by hand, here, and only the trunk pushed", "skip"]


def test_each_line_is_cut_to_fit_the_terminal_so_a_redraw_moves_up_over_every_row():
    shown: list[str] = []
    prompt = "How and where does work reach the trunk in a long-named repository?"
    terminal.pick(prompt, LONG, iter([DOWN, UP, ENTER]), shown.append, Style(False), lambda: 30)
    drawn = rows("".join(shown))
    assert drawn and all(terminal.width(line) < 30 for line in drawn)
    assert "    local      landed on the…" in drawn
    assert drawn[0] == "How and where does work reac…"


def test_the_width_is_measured_again_for_each_redraw():
    shown: list[str] = []
    widths = iter([80, 20, 20])
    terminal.pick("Mode?", LONG, iter([DOWN, ENTER]), shown.append, Style(False), widths.__next__)
    assert "  ❯ local      lan…" not in shown[0]
    assert "    local      lan…" in rows(shown[1])


def test_a_styled_line_cut_short_keeps_its_style_and_closes_it():
    cut = terminal.clip("\x1b[1mbold and long\x1b[0m", 8)
    assert cut == "\x1b[1mbold an…\x1b[0m"


def test_a_line_that_fits_is_left_as_it_is():
    assert terminal.clip("\x1b[1mfits\x1b[0m", 8) == "\x1b[1mfits\x1b[0m"


def test_a_wide_character_is_never_split_by_a_cut():
    assert terminal.clip("ab🏠cd", 4) == "ab…"


def test_wide_characters_take_two_columns_and_escape_codes_none():
    assert terminal.width("\x1b[36m🏠 local\x1b[0m") == 8
    assert terminal.width("e\u0301") == 1


def test_the_prompt_is_styled_unless_no_color_is_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert terminal.style().enabled
    monkeypatch.setenv("NO_COLOR", "1")
    assert not terminal.style().enabled
