"""When output is coloured, and how text is styled."""

import io

import pytest

from cli_kit.colour import BOLD, RESET, Style, wants_colour


class Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_colour_is_used_on_a_terminal():
    assert wants_colour(Terminal())


def test_colour_is_not_used_when_output_is_piped():
    assert not wants_colour(io.StringIO())


def test_force_color_turns_colour_on_when_piped(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert wants_colour(io.StringIO())


def test_no_color_turns_colour_off_even_on_a_terminal_or_forced(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert not wants_colour(Terminal())


def test_a_style_wraps_text_in_its_code():
    assert Style(enabled=True)(BOLD, "name") == f"{BOLD}name{RESET}"


def test_a_style_leaves_text_as_it_is_when_colour_is_off():
    assert Style(enabled=False)(BOLD, "name") == "name"


def test_a_style_leaves_empty_text_empty():
    assert Style(enabled=True)(BOLD, "") == ""
