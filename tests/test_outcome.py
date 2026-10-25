"""Behaviour of saying a slow step is starting."""

import pytest

from cli_kit import outcome


def test_a_step_starting_is_shown_on_stderr_marked_as_under_way(capsys):
    outcome.starting("Waiting for CI")
    assert capsys.readouterr() == ("", "… Waiting for CI\n")


def test_a_step_starting_is_grey_on_a_terminal(capsys, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    outcome.starting("Waiting for CI")
    assert capsys.readouterr().err == "\x1b[38;5;246m… Waiting for CI\x1b[0m\n"


def test_a_step_starting_is_not_a_change(capsys):
    outcome.reset()
    outcome.starting("Waiting for CI")
    assert outcome.changes() == []
