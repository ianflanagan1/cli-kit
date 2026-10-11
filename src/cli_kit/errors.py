"""The problems a command raises for the user to fix. cli.run shows each as a status line."""


class Problem(Exception):
    """A problem the user can fix: a message, then any lines of detail."""

    def __init__(self, message: str, *details: str) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class Precondition(Problem):
    """Something the command needs isn't so, so it tried nothing: ⚠️, and the message is the
    status line, as a sentence. After a change (see outcome.changed), it stops: 🛑."""


class Failure(Problem):
    """A step ran and failed: ❌ <Command> failed., then the message. After a change (see
    outcome.changed), it stops: 🛑."""
