"""Asking the person at the terminal."""

from cli_kit.outcome import Precondition


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
