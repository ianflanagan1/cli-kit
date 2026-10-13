"""What every service's command line has in common."""

import argparse
import re
import sys
from types import ModuleType
from typing import TextIO

from cli_kit import devbox, outcome
from cli_kit.colour import BOLD, CYAN, GREY, YELLOW, Style, wants_colour
from cli_kit.outcome import Done, NothingToDo, Precondition, Problem


class HelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Help that tells what you type from what you fill in: `release <dir> patch|minor|major`.

    Placeholders are in angle brackets, so they don't read as command words, and a fixed set of
    values is written as alternatives. Descriptions keep their line breaks.
    """

    def _metavar_formatter(self, action: argparse.Action, default_metavar: str):
        if action.metavar is None and action.choices is not None:
            alternatives = "|".join(map(str, action.choices))
            return lambda size: (alternatives,) * size if size else alternatives
        name = action.metavar if action.metavar is not None else default_metavar
        if not isinstance(name, str):  # add_argument's check that nargs and metavar agree
            return super()._metavar_formatter(action, default_metavar)
        if not name.startswith("<"):
            name = f"<{name}>"
        return lambda size: (name,) * size if size else name

    def _get_default_metavar_for_optional(self, action: argparse.Action) -> str:
        return action.dest


class ArgumentParser(argparse.ArgumentParser):
    """A parser whose help is laid out by HelpFormatter, and coloured on a terminal.

    cli.run gives every command one. A standalone command, with no subcommands, uses it directly.
    Colour is added as the help is printed, once it's laid out, so it never shifts a column, and
    only when the stream it goes to wants colour.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **{**kwargs, "formatter_class": HelpFormatter})

    def _print_message(self, message: str, file: TextIO | None = None) -> None:
        file = file or sys.stderr
        if message and wants_colour(file):
            message = _colour_help(message, Style(enabled=True))
        super()._print_message(message, file)


def _colour_help(text: str, colour: Style) -> str:
    """Headings bold, options cyan and placeholders yellow."""
    text = re.sub(r"<[\w-]+>", lambda m: colour(YELLOW, m[0]), text)
    text = re.sub(r"(?<![\w-])--?[A-Za-z][\w-]*", lambda m: colour(CYAN, m[0]), text)
    return re.sub(r"^(usage:|[a-z][a-z ]*:$)", lambda m: colour(BOLD, m[0]), text, flags=re.M)


def run(prog: str, description: str, commands: list[ModuleType], argv: list[str] | None) -> int:
    """Parses argv and runs the chosen command, one of the modules in commands.

    Each command module has register(subparsers), which adds its parser and sets its run. run
    returns an outcome or raises a Problem, which is shown as a status line (see outcome).
    `help`, `-h` and `--help` list the commands with their arguments; `help <command>` shows one.
    Returns the exit status: 0 done or nothing to do, 1 a problem, 2 no command. argparse exits 2
    itself on other usage errors.
    """
    parser = ArgumentParser(
        prog=prog, description=description, usage=f"{prog} <command> [args]", add_help=False
    )
    parser.add_argument("-h", "--help", action="store_true")
    subparsers = parser.add_subparsers(
        dest="command", metavar="<command>", prog=prog, parser_class=ArgumentParser
    )
    for command in commands:
        command.register(subparsers)
    help_parser = subparsers.add_parser(
        "help", help="list the commands, or show one command's arguments"
    )
    help_parser.add_argument(
        "topic", nargs="?", metavar="command", choices=list(subparsers.choices)
    )
    args = parser.parse_args(argv)

    if args.command is None and not args.help:
        _print_commands(parser, subparsers, sys.stderr)
        return 2
    if args.help or (args.command == "help" and args.topic is None):
        _print_commands(parser, subparsers, sys.stdout)
        return 0
    if args.command == "help":
        subparsers.choices[args.topic].print_help()
        return 0

    devbox.use_tools()
    outcome.reset()
    try:
        result = args.run(args)
    except Problem as problem:
        print("\n".join(_problem_lines(args.command, problem)), file=sys.stderr)
        return 1
    if isinstance(result, Done):
        print("\n".join([f"✅ {result.summary}", *result.details]))
    elif isinstance(result, NothingToDo):
        print(f"➖ {result.summary}")
    else:
        raise TypeError(f"{prog} {args.command} returned {result!r}, not Done or NothingToDo")
    return 0


def _problem_lines(command: str, problem: Problem) -> list[str]:
    """🛑 after a change, otherwise ⚠️ for a precondition or ❌ for a failure."""
    if changes := outcome.changes():
        return [
            "🛑 Stopped.",
            "Done before it stopped:",
            *(f"  {change}" for change in changes),
            problem.message,
            *problem.details,
            "Fix the cause and run the command again; it skips what's done.",
        ]
    if isinstance(problem, Precondition):
        return [f"⚠️ {problem.message}", *problem.details]
    return [f"❌ {command.capitalize()} failed.", problem.message, *problem.details]


def _print_commands(
    parser: ArgumentParser, subparsers: argparse._SubParsersAction, file: TextIO
) -> None:
    """The overview: usage, description, then each command's arguments and summary.

    On a terminal each command's name is bold and its summary grey, and the rest is coloured as
    any help is.
    """
    colour = Style(enabled=wants_colour(file))
    lines = [parser.format_usage().rstrip(), "", parser.description, "", "commands:"]
    for action in subparsers._choices_actions:
        usage = subparsers.choices[action.dest].format_usage()
        arguments = usage.removeprefix(f"usage: {parser.prog} {action.dest}").replace("[-h]", "")
        synopsis = " ".join([colour(BOLD, action.dest), *arguments.split()])
        lines += [f"  {synopsis}", f"      {colour(GREY, action.help)}"]
    lines += ["", f"Run `{parser.prog} help <command>` for a command's details."]
    parser._print_message("\n".join(lines) + "\n", file)
