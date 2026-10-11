"""Running git and gh."""

import os
import subprocess

from cli_kit.errors import Failure


def output(*args: str, input: str | None = None, env: dict[str, str] | None = None) -> str:
    """Runs a command and returns its stdout without the trailing newline.

    env: variables to set for the command, on top of this process's environment.
    Raises Failure, with the command's stderr, when it exits non-zero.
    """
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        input=input,
        env=os.environ | env if env else None,
        check=False,
    )
    if result.returncode != 0:
        raise Failure(f"{' '.join(args[:3])} failed.", *result.stderr.strip().splitlines())
    return result.stdout.rstrip("\n")


def succeeds(*args: str) -> bool:
    """Runs a command silently and says whether it exited 0."""
    return subprocess.run(args, capture_output=True, check=False).returncode == 0


def run(*args: str) -> None:
    """Runs a command with its output shown to the user. Raises Failure when it exits non-zero."""
    if subprocess.run(args, check=False).returncode != 0:
        raise Failure(f"{' '.join(args[:3])} failed.")
