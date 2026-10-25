"""Claude, through Claude Code run headless, signed in as you, so it needs no API key."""

import json
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import assert_never

from cli_kit.models.agent import Announce, Ended, Failed, Finished, TimedOut

CLAUDE = "claude"


@dataclass(frozen=True)
class ClaudeCode:
    """model: a Claude Code model name or alias, such as "haiku", which follows the latest, or
    None for the one Claude Code is set to use. announce: shows each call's purpose as it
    starts."""

    model: str | None
    timeout_seconds: float
    announce: Announce

    def reply(self, prompt: str, purpose: str) -> str | None:
        """Runs claude with no tools, in an empty directory so no project's CLAUDE.md is
        loaded, and the prompt on stdin."""
        with tempfile.TemporaryDirectory() as empty:
            self.announce(purpose)
            ended = self._claude([*self._model(), "--tools", ""], Path(empty), prompt)
        match ended:
            case Finished(said):
                return said
            case Failed() | TimedOut():
                return None
            case _:
                assert_never(ended)

    def run(self, prompt: str, workspace: Path, readable: Sequence[Path], purpose: str) -> Ended:
        """Runs claude in workspace with its tools, able to read the readable directories too.
        The prompt is an argument, where a slash command such as a skill's is expanded."""
        added = [arg for directory in readable for arg in ("--add-dir", str(directory))]
        self.announce(purpose)
        return self._claude([prompt, *self._model(), *added], workspace, "")

    def _model(self) -> list[str]:
        return ["--model", self.model] if self.model else []

    def _claude(self, args: list[str], cwd: Path, stdin: str) -> Ended:
        try:
            result = subprocess.run(
                [CLAUDE, "-p", *args, "--output-format", "json", "--no-session-persistence"],
                cwd=cwd,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return TimedOut(self.timeout_seconds)
        except OSError as error:
            return Failed(str(error))
        try:
            answer = json.loads(result.stdout)
        except json.JSONDecodeError:
            answer = None
        said = answer.get("result") if isinstance(answer, dict) else None
        if not isinstance(said, str):
            return Failed((result.stdout + result.stderr).strip())
        if result.returncode != 0 or answer.get("is_error"):
            return Failed(said)
        return Finished(said)
