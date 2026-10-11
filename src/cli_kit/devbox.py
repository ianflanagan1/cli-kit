"""A tool's devbox packages, for commands that run outside devbox."""

import os
import sys
from pathlib import Path


def use_tools() -> None:
    """Puts the tool's devbox packages first on the PATH, for the programs commands run.

    So a command run from .venv/bin, without starting devbox, still runs the gh that devbox
    pins. .venv is in the root of the tool's project, next to .devbox. Does nothing outside one.
    """
    tools = str(Path(sys.prefix).parent / ".devbox" / "nix" / "profile" / "default" / "bin")
    path = os.environ.get("PATH", "")
    if Path(tools).is_dir() and not path.startswith(tools + os.pathsep):
        os.environ["PATH"] = tools + os.pathsep + path
