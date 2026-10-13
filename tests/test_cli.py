"""The command line every tool shares: choosing a command, help, outcomes and exit statuses."""

import argparse
import re
import sys
from collections.abc import Callable
from types import SimpleNamespace

import pytest

from cli_kit import cli, devbox, outcome
from cli_kit.colour import BOLD, CYAN, GREY, RESET, YELLOW
from cli_kit.outcome import Done, Failure, NothingToDo, Precondition


def command(
    name: str,
    summary: str,
    *arguments: str,
    does: Callable[[argparse.Namespace], object] | None = None,
) -> SimpleNamespace:
    """A stand-in command module. Its run records its arguments, then does `does`."""
    ran: list[argparse.Namespace] = []

    def run(args: argparse.Namespace) -> object:
        ran.append(args)
        return does(args) if does else Done("Made.")

    def register(subparsers: cli.Subparsers) -> None:
        parser = subparsers.add_parser(name, help=summary, description=f"All about {name}.")
        for argument in arguments:
            parser.add_argument(argument, nargs="?" if argument.startswith("opt") else None)
        parser.set_defaults(run=run)

    return SimpleNamespace(register=register, ran=ran)


def doing(does: Callable[[argparse.Namespace], object]) -> list[SimpleNamespace]:
    return [command("make", "make a thing", does=does)]


def raising(problem: Exception) -> Callable[[argparse.Namespace], object]:
    def does(args: argparse.Namespace) -> object:
        raise problem

    return does


@pytest.fixture
def commands() -> list[SimpleNamespace]:
    return [command("make", "make a thing", "dir", "optname"), command("drop", "drop it", "thing")]


def run(commands: list[SimpleNamespace], *argv: str) -> int:
    return cli.run("tool", "Do things.", commands, list(argv))


def test_runs_the_chosen_command_with_its_arguments(commands, capsys):
    assert run(commands, "drop", "x") == 0
    assert commands[1].ran[0].thing == "x"


# Outcomes, shown as the status lines of the skill conventions


def test_done_prints_a_tick_line_then_its_details_and_exits_0(capsys):
    assert run(doing(lambda args: Done("Archived.", "https://example.com/a")), "make") == 0
    assert capsys.readouterr().out == "✅ Archived.\nhttps://example.com/a\n"


def test_nothing_to_do_prints_a_dash_line_and_exits_0(capsys):
    assert run(doing(lambda args: NothingToDo("Already archived.")), "make") == 0
    assert capsys.readouterr().out == "➖ Already archived.\n"


def test_an_unmet_precondition_prints_a_warning_line_and_details_on_stderr(capsys):
    problem = Precondition("Uncommitted changes in /a.", "Commit them first.")
    assert run(doing(raising(problem)), "make") == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "⚠️ Uncommitted changes in /a.\nCommit them first.\n"


def test_a_failure_prints_a_cross_line_naming_the_command_then_the_error(capsys):
    assert run(doing(raising(Failure("gh broke.", "log line"))), "make") == 1
    assert capsys.readouterr().err == "❌ Make failed.\ngh broke.\nlog line\n"


@pytest.mark.parametrize("problem", [Failure("Push failed."), Precondition("Origin is wrong.")])
def test_a_problem_after_a_change_stops_with_what_was_done_and_how_to_resume(problem, capsys):
    def does(args: argparse.Namespace) -> object:
        outcome.changed("Created me/thing")
        outcome.changed("Added origin")
        raise problem

    assert run(doing(does), "make") == 1
    captured = capsys.readouterr()
    assert captured.out == "Created me/thing\nAdded origin\n"
    assert captured.err == (
        "🛑 Stopped.\n"
        "Done before it stopped:\n"
        "  Created me/thing\n"
        "  Added origin\n"
        f"{problem.message}\n"
        "Fix the cause and run the command again; it skips what's done.\n"
    )


def test_changes_from_an_earlier_run_do_not_count(capsys):
    def change(args: argparse.Namespace) -> object:
        outcome.changed("Created me/thing")
        return Done("Made.")

    run(doing(change), "make")
    assert run(doing(raising(Failure("gh broke."))), "make") == 1
    assert capsys.readouterr().err.startswith("❌ Make failed.")


def test_a_command_must_end_with_an_outcome():
    with pytest.raises(TypeError, match="returned None, not Done or NothingToDo"):
        run(doing(lambda args: None), "make")


# Help


@pytest.mark.parametrize("argv", [["help"], ["--help"], ["-h"]])
def test_help_lists_every_command_with_its_arguments_and_summary(commands, capsys, argv):
    assert run(commands, *argv) == 0
    out = capsys.readouterr().out
    assert "Do things." in out
    assert "make <dir> [<optname>]" in out
    assert "make a thing" in out
    assert "drop <thing>" in out
    assert "drop it" in out
    assert "help [<command>]" in out


def test_help_writes_arguments_as_placeholders_so_they_differ_from_commands(commands, capsys):
    assert run(commands, "help", "make") == 0
    out = capsys.readouterr().out
    assert out.startswith("usage: tool make [-h] <dir> [<optname>]")
    assert "  <dir>" in out


def test_help_writes_a_fixed_set_of_values_as_alternatives(capsys):
    def register(subparsers: cli.Subparsers) -> None:
        parser = subparsers.add_parser("bump", help="bump the version")
        parser.add_argument("level", choices=["patch", "minor", "major"])
        parser.add_argument("--style", choices=["v", "bare"])

    cli.run("tool", "Do things.", [SimpleNamespace(register=register)], ["help"])
    assert "bump [--style v|bare] patch|minor|major" in capsys.readouterr().out


def test_help_names_an_options_value_in_lower_case(capsys):
    def register(subparsers: cli.Subparsers) -> None:
        subparsers.add_parser("tag", help="tag it").add_argument("--message")

    cli.run("tool", "Do things.", [SimpleNamespace(register=register)], ["help"])
    assert "tag [--message <message>]" in capsys.readouterr().out


def test_a_commands_description_keeps_its_line_breaks(capsys):
    def register(subparsers: cli.Subparsers) -> None:
        subparsers.add_parser("list", help="list", description="Steps:\n  1. one\n  2. two")

    cli.run("tool", "Do things.", [SimpleNamespace(register=register)], ["help", "list"])
    assert "Steps:\n  1. one\n  2. two" in capsys.readouterr().out


def plain(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def test_help_on_a_terminal_colours_headings_commands_summaries_options_and_placeholders(
    commands, capsys, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("FORCE_COLOR", "1")
    run(commands, "help")
    out = capsys.readouterr().out
    assert f"{BOLD}commands:{RESET}" in out
    assert f"  {BOLD}make{RESET} {YELLOW}<dir>{RESET} [{YELLOW}<optname>{RESET}]" in out
    assert f"      {GREY}make a thing{RESET}" in out

    run(commands, "help", "make")
    out = capsys.readouterr().out
    assert out.startswith(f"{BOLD}usage:{RESET} tool make [{CYAN}-h{RESET}]")
    assert f"{BOLD}positional arguments:{RESET}\n  {YELLOW}<dir>{RESET}" in out
    assert f"{CYAN}-h{RESET}, {CYAN}--help{RESET}" in out


@pytest.mark.parametrize("argv", [["help"], ["help", "make"]])
def test_coloured_help_is_laid_out_exactly_as_plain_help(
    commands, capsys, monkeypatch: pytest.MonkeyPatch, argv
):
    run(commands, *argv)
    uncoloured = capsys.readouterr().out
    monkeypatch.setenv("FORCE_COLOR", "1")
    run(commands, *argv)
    coloured = capsys.readouterr().out
    assert coloured != uncoloured
    assert plain(coloured) == uncoloured


def test_help_that_is_piped_has_no_colour(commands, capsys):
    run(commands, "help")
    run(commands, "help", "make")
    assert "\x1b" not in capsys.readouterr().out


def test_the_command_list_shown_for_a_missing_command_is_coloured_for_stderr(
    commands, capsys, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(cli, "wants_colour", lambda stream: stream is sys.stderr)
    assert cli.run("tool", "Do things.", commands, []) == 2
    assert f"{BOLD}commands:{RESET}" in capsys.readouterr().err


def test_a_standalone_command_gets_the_same_help(capsys, monkeypatch: pytest.MonkeyPatch):
    parser = cli.ArgumentParser(prog="tidy", description="Tidies:\n  1. one")
    parser.add_argument("root", nargs="?")
    parser.add_argument("--level", choices=["low", "high"])
    parser.print_help()
    out = capsys.readouterr().out
    assert out.startswith("usage: tidy [-h] [--level low|high] [<root>]")
    assert "Tidies:\n  1. one" in out

    monkeypatch.setenv("FORCE_COLOR", "1")
    parser.print_help()
    assert f"{BOLD}usage:{RESET}" in capsys.readouterr().out


def test_help_for_a_command_shows_that_commands_own_help(commands, capsys):
    assert run(commands, "help", "make") == 0
    out = capsys.readouterr().out
    assert out.startswith("usage: tool make")
    assert "All about make." in out


def test_help_for_an_unknown_command_is_a_usage_error(commands, capsys):
    with pytest.raises(SystemExit) as exit:
        run(commands, "help", "nope")
    assert exit.value.code == 2


def test_without_a_command_the_command_list_goes_to_stderr_with_exit_status_2(commands, capsys):
    assert run(commands) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "make <dir> [<optname>]" in captured.err


def test_an_unknown_command_is_a_usage_error(commands, capsys):
    with pytest.raises(SystemExit) as exit:
        run(commands, "nope")
    assert exit.value.code == 2


def test_commands_run_with_the_tools_devbox_packages_on_the_path(
    commands, monkeypatch: pytest.MonkeyPatch
):
    calls = []
    monkeypatch.setattr(devbox, "use_tools", lambda: calls.append(True))
    run(commands, "drop", "x")
    assert calls == [True]
