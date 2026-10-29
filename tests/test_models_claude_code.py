"""The Claude Code model and agent, with claude replaced by a script."""

import json
import stat
from pathlib import Path

import pytest

from cli_kit.models import claude_code
from cli_kit.models.agent import Failed, Finished, TimedOut
from cli_kit.models.claude_code import ClaudeCode


def ignore(line: str) -> None:
    pass


FINISHED = json.dumps({"type": "result", "is_error": False, "result": "✅ Committed."})


class Said:
    """An announcer that records what it was told, and whether claude had run by then."""

    def __init__(self, log: Path) -> None:
        self.log = log
        self.lines: list[str] = []
        self.before_claude: list[bool] = []

    def __call__(self, line: str) -> None:
        self.lines.append(line)
        self.before_claude.append(not self.log.exists())


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
    assert ClaudeCode("haiku", 5, ignore).reply("Describe it.", "Describing it") == "Sorts socks."
    called = log.read_text().splitlines()
    assert called[:3] == ["--print", "--model", "haiku"]
    assert called[called.index("--tools") + 1] == ""
    assert called[-1] == "Describe it."


def test_an_error_result_is_no_reply(claude):
    answer = json.dumps({"type": "result", "is_error": True, "result": "Not logged in"})
    claude(f"echo '{answer}'")
    assert ClaudeCode("haiku", 5, ignore).reply("Describe it.", "Describing it") is None


def test_a_failed_run_is_no_reply(claude):
    claude("exit 1")
    assert ClaudeCode("haiku", 5, ignore).reply("Describe it.", "Describing it") is None


def test_output_that_is_not_json_is_no_reply(claude):
    claude("echo hello")
    assert ClaudeCode("haiku", 5, ignore).reply("Describe it.", "Describing it") is None


def test_a_missing_claude_is_no_reply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(claude_code, "CLAUDE", str(tmp_path / "missing"))
    assert ClaudeCode("haiku", 5, ignore).reply("Describe it.", "Describing it") is None


def test_a_run_that_takes_longer_than_its_timeout_is_no_reply(claude):
    claude("sleep 5")
    assert ClaudeCode("haiku", 0.2, ignore).reply("Describe it.", "Describing it") is None


# --- Agent runs


def test_an_agent_runs_the_prompt_in_the_workspace_able_to_read_the_other_directories(
    claude, tmp_path: Path
):
    workspace, shared = tmp_path / "repo", tmp_path / "shared"
    workspace.mkdir()
    log = claude(f"pwd > {tmp_path / 'cwd'}; echo '{FINISHED}'")
    ClaudeCode("opus", 5, ignore).run("/ianf-commit", workspace, [shared], "Committing")
    called = log.read_text().splitlines()
    assert called[:4] == ["--print", "/ianf-commit", "--model", "opus"]
    assert called[called.index("--add-dir") + 1] == str(shared)
    assert "--tools" not in called
    assert Path((tmp_path / "cwd").read_text().strip()).resolve() == workspace.resolve()


def test_with_no_model_an_agent_runs_on_the_one_claude_code_is_set_to(claude, tmp_path: Path):
    log = claude(f"echo '{FINISHED}'")
    ClaudeCode(None, 5, ignore).run("/ianf-commit", tmp_path, [], "Committing")
    assert "--model" not in log.read_text().splitlines()


def test_an_agent_run_that_finishes_gives_what_it_said(claude, tmp_path: Path):
    claude(f"echo '{FINISHED}'")
    assert ClaudeCode(None, 5, ignore).run("/ianf-commit", tmp_path, [], "Committing") == Finished(
        "✅ Committed."
    )


def test_an_agent_run_whose_result_is_an_error_failed_with_what_it_said(claude, tmp_path: Path):
    answer = json.dumps({"type": "result", "is_error": True, "result": "Not logged in"})
    claude(f"echo '{answer}'")
    assert ClaudeCode(None, 5, ignore).run("/ianf-commit", tmp_path, [], "Committing") == Failed(
        "Not logged in"
    )


def test_an_agent_run_with_output_that_is_not_json_failed_with_its_output(claude, tmp_path: Path):
    claude("echo out; echo err >&2; exit 1")
    assert ClaudeCode(None, 5, ignore).run("/ianf-commit", tmp_path, [], "Committing") == Failed(
        "out\nerr"
    )


def test_an_agent_run_of_a_missing_claude_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(claude_code, "CLAUDE", str(tmp_path / "missing"))
    assert isinstance(
        ClaudeCode(None, 5, ignore).run("/ianf-commit", tmp_path, [], "Committing"), Failed
    )


def test_an_agent_run_that_takes_longer_than_its_timeout_timed_out(claude, tmp_path: Path):
    claude("sleep 5")
    assert ClaudeCode(None, 0.2, ignore).run(
        "/ianf-commit", tmp_path, [], "Committing"
    ) == TimedOut(0.2)


# --- Saying what's starting


def test_a_reply_says_its_purpose_before_claude_runs(claude, tmp_path: Path):
    answer = json.dumps({"type": "result", "is_error": False, "result": "Sorts socks."})
    log = claude(f"echo '{answer}'")
    said = Said(log)
    ClaudeCode("haiku", 5, said).reply("Describe it.", "Writing a description for me/thing")
    assert said.lines == ["Writing a description for me/thing"]
    assert said.before_claude == [True]


def test_an_agent_run_says_its_purpose_before_claude_runs(claude, tmp_path: Path):
    log = claude(f"echo '{FINISHED}'")
    said = Said(log)
    ClaudeCode(None, 5, said).run("/ianf-commit", tmp_path, [], "Committing with /ianf-commit")
    assert said.lines == ["Committing with /ianf-commit"]
    assert said.before_claude == [True]
