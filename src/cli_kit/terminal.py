"""Asking the person at the terminal."""

import os
import re
import termios
import tty
import unicodedata
from collections.abc import Callable, Iterator, Sequence
from enum import Enum
from typing import assert_never

from cli_kit.colour import BOLD, CYAN, RESET, Style
from cli_kit.outcome import Precondition

# ANSI escape codes for moving about the terminal.
_CLEAR_LINE = "\r\x1b[2K"
_CLEAR_BELOW = "\x1b[J"
_HIDE_CURSOR = "\x1b[?25l"
_SHOW_CURSOR = "\x1b[?25h"
_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_FALLBACK_COLUMNS = 80
"""How wide to take a terminal that can't say."""


def style() -> Style:
    """How text shown on the terminal is styled, as choose styles it: coloured unless NO_COLOR
    is set. For a caller styling the prompt it passes to choose."""
    return Style(enabled=not os.environ.get("NO_COLOR"))


def width(text: str) -> int:
    """How many columns text takes in a terminal: two for a wide character, such as most emoji,
    none for an escape code or a character that only modifies the one before it."""
    return sum(_char_width(c) for c in _ESCAPE.sub("", text))


def clip(text: str, columns: int) -> str:
    """text cut to fit in columns, ending in … where it's cut, with its escape codes kept and its
    style closed after the cut. A wide character is never split."""
    if width(text) <= columns:
        return text
    kept: list[str] = []
    used = 0
    for token in re.finditer(rf"{_ESCAPE.pattern}|.", text, re.DOTALL):
        piece = token.group()
        if _ESCAPE.fullmatch(piece):
            kept.append(piece)
            continue
        used += _char_width(piece)
        if used > columns - 1:
            break
        kept.append(piece)
    return "".join(kept) + "…" + (RESET if _ESCAPE.search(text) else "")


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
            return pick(prompt, options, _keys(fd), show, style(), lambda: _columns(fd))
        finally:
            show(_SHOW_CURSOR)
            termios.tcsetattr(fd, termios.TCSANOW, saved)


def pick(
    prompt: str,
    options: Sequence[str],
    keys: Iterator[bytes],
    show: Callable[[str], None],
    style: Style,
    columns: Callable[[], int],
) -> int | None:
    """choose, reading each key pressed from keys and showing what's drawn with show: the index
    of the option chosen, or None when keys run out first.

    A redraw moves up a row for each line drawn, so each line is cut to fit in the terminal, as
    wide as columns says at the time, rather than wrapped onto rows it wouldn't move up over. It
    stops a column short, as some terminals wrap a line that fills the last one.
    """
    current = 0
    fit = columns() - 1
    show(f"{clip(prompt, fit)}\n{_options(options, current, style, fit)}")
    for pressed in keys:
        match _key(pressed):
            case _Key.UP:
                current = max(current - 1, 0)
            case _Key.DOWN:
                current = min(current + 1, len(options) - 1)
            case _Key.ENTER:
                fit = columns() - 1
                chosen = clip(f"  {style(CYAN, f'❯ {options[current]}')}", fit)
                show(f"\x1b[{len(options) + 1}F{_CLEAR_BELOW}{clip(prompt, fit)}\n{chosen}\n")
                return current
            case _Key.OTHER:
                continue
            case _:
                assert_never(pressed)
        show(f"\x1b[{len(options)}F{_options(options, current, style, columns() - 1)}")
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


def _options(options: Sequence[str], current: int, style: Style, columns: int) -> str:
    """Each option on its own line, cut to fit in columns, the current one marked."""
    return "".join(
        f"{_CLEAR_LINE}{clip(f'  {style(BOLD + CYAN, f"❯ {option}")}', columns)}\n"
        if index == current
        else f"{_CLEAR_LINE}{clip(f'    {option}', columns)}\n"
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


def _columns(fd: int) -> int:
    """How wide the terminal fd is, or the fallback when it can't say."""
    try:
        return os.get_terminal_size(fd).columns or _FALLBACK_COLUMNS
    except OSError:
        return _FALLBACK_COLUMNS


def _char_width(character: str) -> int:
    if unicodedata.combining(character) or character in "️‍":
        return 0
    return 2 if unicodedata.east_asian_width(character) in "WF" else 1
