"""Claude, through Claude Code run headless, signed in as you, so it needs no API key."""

import json
import subprocess
import tempfile
from dataclasses import dataclass

CLAUDE = "claude"


@dataclass(frozen=True)
class ClaudeCode:
    """model: a Claude Code model name or alias, such as "haiku", which follows the latest."""

    model: str
    timeout_seconds: float

    def reply(self, prompt: str) -> str | None:
        """Runs claude with no tools, in an empty directory so no project's CLAUDE.md is
        loaded, and the prompt on stdin."""
        with tempfile.TemporaryDirectory() as empty:
            try:
                result = subprocess.run(
                    [
                        CLAUDE,
                        "-p",
                        "--model",
                        self.model,
                        "--tools",
                        "",
                        "--output-format",
                        "json",
                        "--no-session-persistence",
                    ],
                    cwd=empty,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )
            except (OSError, subprocess.TimeoutExpired):
                return None
        if result.returncode != 0:
            return None
        try:
            answer = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        if not isinstance(answer, dict) or answer.get("is_error"):
            return None
        text = answer.get("result")
        return text if isinstance(text, str) else None
