"""Fixtures shared by the tests."""

import pytest


@pytest.fixture(autouse=True)
def no_colour_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts without FORCE_COLOR or NO_COLOR, whatever the shell running it has."""
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
