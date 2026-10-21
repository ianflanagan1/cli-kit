"""How a command ends, which cli.run shows as one status line.

This implements the scheme the improve-skill plugin's skill conventions define, so a command
reports like a skill does:
https://github.com/ianflanagan1/claude-improve-skill/blob/main/skills/improve-skill/references/skill-conventions.md#status-line

    ✅ Done          the command changed state as asked; then its result, such as a URL
    ➖ NothingToDo   there was nothing to do
    ⚠️ Precondition  something it needs isn't so, so it tried nothing (raised)
    ❌ Failure       a step ran and failed (raised)
    🛑 Stopped       either problem, after the command had changed something

A command returns Done or NothingToDo, or raises Precondition or Failure. Each change it makes
goes through changed(), so a later problem can say what was done before it stopped.
"""


class Done:
    """The command changed state as asked. summary is a sentence, such as "Archived."; details
    are the result, such as a URL, in as few lines as it takes."""

    def __init__(self, summary: str, *details: str) -> None:
        self.summary = summary
        self.details = details


class NothingToDo:
    """There was nothing to do. summary is a sentence, such as "Already archived."."""

    def __init__(self, summary: str) -> None:
        self.summary = summary


class Problem(Exception):
    """A problem the user can fix: a message, then any lines of detail."""

    def __init__(self, message: str, *details: str) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class Precondition(Problem):
    """Something the command needs isn't so, so it tried nothing: ⚠️, and the message is the
    status line, as a sentence. After a change (see changed), it stops: 🛑."""


class Failure(Problem):
    """A step ran and failed: ❌ <Command> failed., then the message. After a change (see
    changed), it stops: 🛑."""


_changes: list[str] = []


def changed(description: str) -> None:
    """Shows and records a change the command has made, such as "Created me/thing"."""
    print(description)
    _changes.append(description)


def changes() -> list[str]:
    """The changes recorded since the command started."""
    return list(_changes)


def reset() -> None:
    _changes.clear()
