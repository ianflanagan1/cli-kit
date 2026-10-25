"""Asking the person at the terminal."""

import os
import termios
import tty
from collections.abc import Callable, Iterator, Sequence
from enum import Enum
from typing import assert_never

from cli_kit.colour import BOLD, CYAN, Style
from cli_kit.outcome import Precondition

# ANSI escape codes for moving about the terminal.
_CLEAR_LINE = "\r\x1b[2K"
_CLEAR_BELOW = "\x1b[J"
_HIDE_CURSOR = "\x1b[?25l"
_SHOW_CURSOR = "\x1b[?25h"


def ask(prompt: str) -> str:
    """Shows prompt on the terminal and returns the line typed there, without surrounding space.

    Reads the terminal itself rather than stdin, so piping an answer in doesn't answer it.
    Raises Precondition when there is no terminal, as when an agent runs the command.
    """
    try:
        terminal = open("/dev/tty", "r+")
    except OSError:
        raise Precondition("No terminal to confirm at.", "Run it yourself.") from None
    with terminal:
        terminal.write(prompt)
        terminal.flush()
        return terminal.readline().strip()


def choose(prompt: str, options: Sequence[str]) -> int | None:
    """Shows prompt on the terminal with options under it, and returns the index of the one
    chosen: the up and down arrows move between them, and Enter chooses.

    Reads the terminal itself rather than stdin, as ask does. None when there is no terminal, as
    when an agent runs the command, so the caller carries on as if nothing was chosen.
    """
    try:
        # Unbuffered bytes, as a text wrapper opened for reading and writing must be seekable.
        terminal = open("/dev/tty", "r+b", buffering=0)
    except OSError:
        return None
    with terminal:
        fd = terminal.fileno()
        saved = termios.tcgetattr(fd)
        # TCSANOW keeps keys already typed, which TCSAFLUSH would throw away.
        tty.setcbreak(fd, termios.TCSANOW)

        def show(text: str) -> None:
            terminal.write(text.encode())

        show(_HIDE_CURSOR)
        try:
            style = Style(enabled=not os.environ.get("NO_COLOR"))
            return pick(prompt, options, _keys(fd), show, style)
        finally:
            show(_SHOW_CURSOR)
            termios.tcsetattr(fd, termios.TCSANOW, saved)


def pick(
    prompt: str,
    options: Sequence[str],
    keys: Iterator[bytes],
    show: Callable[[str], None],
    style: Style,
) -> int | None:
    """choose, reading each key pressed from keys and showing what's drawn with show: the index
    of the option chosen, or None when keys run out first."""
    current = 0
    show(f"{prompt}\n{_options(options, current, style)}")
    for pressed in keys:
        match _key(pressed):
            case _Key.UP:
                current = max(current - 1, 0)
            case _Key.DOWN:
                current = min(current + 1, len(options) - 1)
            case _Key.ENTER:
                chosen = style(CYAN, options[current])
                show(f"\x1b[{len(options) + 1}F{_CLEAR_BELOW}{prompt} {chosen}\n")
                return current
            case _Key.OTHER:
                continue
            case _:
                assert_never(pressed)
        show(f"\x1b[{len(options)}F{_options(options, current, style)}")
    return None


class _Key(Enum):
    UP = "up"
    DOWN = "down"
    ENTER = "enter"
    OTHER = "other"


def _key(pressed: bytes) -> _Key:
    match pressed:
        case b"\x1b[A" | b"\x1bOA":
            return _Key.UP
        case b"\x1b[B" | b"\x1bOB":
            return _Key.DOWN
        case b"\n" | b"\r":
            return _Key.ENTER
        case _:
            return _Key.OTHER


def _options(options: Sequence[str], current: int, style: Style) -> str:
    """Each option on its own line, the current one marked."""
    return "".join(
        f"{_CLEAR_LINE}  {style(BOLD + CYAN, f'❯ {option}')}\n"
        if index == current
        else f"{_CLEAR_LINE}    {option}\n"
        for index, option in enumerate(options)
    )


def _keys(fd: int) -> Iterator[bytes]:
    """Each key pressed on the terminal fd, an arrow's escape sequence as one."""
    while True:
        pressed = os.read(fd, 1)
        if not pressed:
            return
        if pressed == b"\x1b":
            pressed += os.read(fd, 2)
        yield pressed
