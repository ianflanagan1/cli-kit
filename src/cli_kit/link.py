"""Links a tool's commands onto your PATH: each one in its pyproject.toml's [project.scripts],
from the project's .venv/bin into $XDG_BIN_HOME, or ~/.local/bin without it.

Each tool's `devbox run -- task setup` runs it after `uv sync`. The commands are console
scripts pointing at the Python devbox pins, so they run without starting devbox. Run it again
after moving a checkout: a link left dangling is replaced, but a command of the same name from
elsewhere is left alone.
"""

import os
import shutil
import sys
import tomllib
from pathlib import Path

from cli_kit import cli
from cli_kit.outcome import Done, NothingToDo, Precondition, changed


def main(argv: list[str] | None = None) -> int:
    parser = cli.ArgumentParser(prog="python -m cli_kit.link", description=__doc__)
    parser.add_argument("project", nargs="?", default=".", help="default: the current directory")
    args = parser.parse_args(argv)
    return cli.finish("link", lambda: link(Path(args.project).resolve(), bin_dir()))


def bin_dir() -> Path:
    """Where commands are linked: $XDG_BIN_HOME, or ~/.local/bin."""
    return Path(os.environ.get("XDG_BIN_HOME") or Path.home() / ".local" / "bin")


def link(project: Path, bin_dir: Path) -> Done | NothingToDo:
    """Links each of project's commands into bin_dir, checking every one before linking any."""
    pyproject = project / "pyproject.toml"
    if not pyproject.is_file():
        raise Precondition(f"No pyproject.toml in {project}.")
    commands = list(tomllib.loads(pyproject.read_text()).get("project", {}).get("scripts", {}))
    if not commands:
        return NothingToDo("No commands to link.")

    sources = {command: project / ".venv" / "bin" / command for command in commands}
    if unbuilt := [c for c, source in sources.items() if not os.access(source, os.X_OK)]:
        raise Precondition(
            f"Not built: {', '.join(unbuilt)}.",
            f"Run `devbox run -- task setup` in {project}, which builds them with `uv sync` first.",
        )
    todo = [c for c in commands if _target(bin_dir / c) != str(sources[c])]
    if taken := [c for c in todo if (bin_dir / c).exists()]:
        raise Precondition(
            f"{bin_dir} already has {', '.join(taken)}, from elsewhere.",
            *(f"  {bin_dir / c} → {_target(bin_dir / c) or 'a file'}" for c in taken),
            "Remove them if they're old copies of these, then run this again.",
        )

    problems = _path_problems(bin_dir, commands)
    if not todo:
        if problems:
            raise Precondition(*problems[0])
        return NothingToDo("Already linked.")
    bin_dir.mkdir(parents=True, exist_ok=True)
    for command in todo:
        target = bin_dir / command
        target.unlink(missing_ok=True)  # a link left dangling by a moved checkout
        target.symlink_to(sources[command])
        changed(f"Linked {target} → {sources[command]}")
    return Done("Linked.", *(line for problem in problems for line in problem))


def _target(path: Path) -> str | None:
    """Where the link at path points, or None when it isn't a link."""
    return os.readlink(path) if path.is_symlink() else None


def _path_problems(bin_dir: Path, commands: list[str]) -> list[tuple[str, str]]:
    """What would stop the linked commands running from your PATH: each a problem and advice."""
    if str(bin_dir) not in os.environ.get("PATH", "").split(os.pathsep):
        return [
            (
                f"{bin_dir} isn't on your PATH.",
                "Add it in your shell's profile, so these commands run.",
            )
        ]
    problems = []
    for command in commands:
        found = shutil.which(command)
        if found and Path(found) != bin_dir / command:
            problems.append(
                (
                    f"`{command}` runs {found}, which is earlier on your PATH.",
                    f"Remove it, or move {bin_dir} ahead of it in your shell's profile.",
                )
            )
    return problems


if __name__ == "__main__":
    sys.exit(main())
