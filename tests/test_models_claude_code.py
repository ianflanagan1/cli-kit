"""The Claude Code model, with claude replaced by a script."""

import json
import stat
from pathlib import Path

import pytest

from cli_kit.models import claude_code
from cli_kit.models.claude_code import ClaudeCode


@pytest.fixture
def claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Makes claude a script that records its arguments and stdin, then runs body."""
    script = tmp_path / "claude"
    log = tmp_path / "log"

    def install(body: str) -> Path:
        script.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > {log}\ncat >> {log}\n{body}\n')
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        monkeypatch.setattr(claude_code, "CLAUDE", str(script))
        return log

    return install


def test_the_prompt_goes_to_claude_on_stdin_with_no_tools(claude):
    answer = json.dumps({"type": "result", "is_error": False, "result": "Sorts socks."})
    log = claude(f"echo '{answer}'")
    assert ClaudeCode("haiku", 5).reply("Describe it.") == "Sorts socks."
    called = log.read_text().splitlines()
    assert called[:3] == ["-p", "--model", "haiku"]
    assert called[called.index("--tools") + 1] == ""
    assert called[-1] == "Describe it."


def test_an_error_result_is_no_reply(claude):
    answer = json.dumps({"type": "result", "is_error": True, "result": "Not logged in"})
    claude(f"echo '{answer}'")
    assert ClaudeCode("haiku", 5).reply("Describe it.") is None


def test_a_failed_run_is_no_reply(claude):
    claude("exit 1")
    assert ClaudeCode("haiku", 5).reply("Describe it.") is None


def test_output_that_is_not_json_is_no_reply(claude):
    claude("echo hello")
    assert ClaudeCode("haiku", 5).reply("Describe it.") is None


def test_a_missing_claude_is_no_reply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(claude_code, "CLAUDE", str(tmp_path / "missing"))
    assert ClaudeCode("haiku", 5).reply("Describe it.") is None


def test_a_run_that_takes_longer_than_its_timeout_is_no_reply(claude):
    claude("sleep 5")
    assert ClaudeCode("haiku", 0.2).reply("Describe it.") is None
