"""Agents a tool can have do work in a workspace, and how a run ended, for the tool to judge
by what it changed.

A reply sees only the prompt and the model's global context. An agent runs a session in a
workspace, where it can read its files and change them. A tool depends on Agent, the port;
ClaudeCode implements it.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, final

type Announce = Callable[[str], None]
"""Shows that a slow step is starting, given its purpose: outcome.starting in a command, or
the tool's own log."""


@final
@dataclass(frozen=True)
class Finished:
    """It ran to the end. said: its final message."""

    said: str


@final
@dataclass(frozen=True)
class Failed:
    """It couldn't start, or ended in an error. said: its error, or all it printed."""

    said: str


@final
@dataclass(frozen=True)
class TimedOut:
    """It was stopped after_seconds in, having perhaps done some of its work."""

    after_seconds: float


type Ended = Finished | Failed | TimedOut


class Agent(Protocol):
    def run(self, prompt: str, workspace: Path, readable: Sequence[Path], purpose: str) -> Ended:
        """Runs a session on prompt in workspace, able to read the readable directories too, and
        says how it ended. Announces purpose first, such as "Committing with /ianf-commit", as
        it can take minutes. Judge what it did by the workspace, not by what it said."""
        ...
