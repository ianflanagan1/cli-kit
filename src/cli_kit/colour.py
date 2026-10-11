"""Colour on a terminal, following no-color.org and FORCE_COLOR."""

import os
import sys
from dataclasses import dataclass
from typing import TextIO

# ANSI escape codes for terminal styles.
RESET = "\x1b[0m"
BOLD = "\x1b[1m"
GREY = "\x1b[38;5;246m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
CYAN = "\x1b[36m"


def wants_colour(stream: TextIO = sys.stdout) -> bool:
    """Colour when stream is a terminal, or when FORCE_COLOR is set, unless NO_COLOR is set."""
    if os.environ.get("NO_COLOR"):
        return False
    return bool(os.environ.get("FORCE_COLOR")) or stream.isatty()


@dataclass
class Style:
    enabled: bool

    def __call__(self, code: str, text: str) -> str:
        """text in the style given by code, or as it is when colour is off or text is empty."""
        return f"{code}{text}{RESET}" if self.enabled and text else text
