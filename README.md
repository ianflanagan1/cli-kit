# cli-kit

The framework my command line tools are built on: subcommands, help, exit statuses, running other programs, credentials and terminal prompts. Each tool is its own repository under `~/projects/cli` and depends on cli-kit, so every command behaves the same way.

| Tool | Commands | What for |
|---|---|---|
| [repo-tools](../repo-tools) | `github`, `packagist`, `repo-list`, `repo-fix` | Publishing repos on GitHub and Packagist, and reporting and fixing the state of every repo under `~/projects` |

## How every command behaves

cli-kit gives every tool built on `cli_kit.cli.run`:

- **Help:** `<tool> help`, `-h`, `--help`, or no command at all, lists the commands with their arguments. `<tool> help <command>` or `<tool> <command> --help` shows one command in full. Placeholders are in angle brackets and a fixed set of values is written as alternatives, `release <dir> patch|minor|major`, so what you type reads differently from what you fill in. On a terminal, headings and command names are bold, command summaries grey, options cyan and placeholders yellow; `NO_COLOR` turns colour off and `FORCE_COLOR` keeps it when piping. A standalone command such as repo-list gets the same by building its parser with `cli.ArgumentParser`. For colour in a command's own output, use `cli_kit.colour`.
- **Outcomes:** every command ends with one status line, in the same scheme as my skills:

  | Line | Outcome | A command… | Exit |
  |---|---|---|---|
  | `✅ Published.` and the result, such as a URL | it changed state as asked | returns `Done(summary, *details)` | 0 |
  | `➖ Already archived.` | there was nothing to do | returns `NothingToDo(summary)` | 0 |
  | `⚠️ Uncommitted changes in …` | something it needs isn't so, so it tried nothing | raises `Precondition(message, *details)` | 1 |
  | `❌ Publish failed.` and the error | a step ran and failed | raises `Failure(message, *details)` | 1 |
  | `🛑 Stopped.`, what was done, the error, how to resume | either problem, after it had changed something | calls `outcome.changed(...)` for each change | 1 |

  Usage errors exit 2. ✅ and ➖ go to stdout; the rest to stderr. A command that returns anything else is a bug, and `cli.run` raises. Check preconditions before the first change, so a problem with them is ⚠️, not 🛑. All four come from `cli_kit.outcome`. The scheme comes from the improve-skill plugin's `skill-conventions.md`, and `cli_kit/outcome.py` names that file: change both together.
- **Any other exception** is a bug, and shows a traceback.
- **Programs it runs** come from the tool's devbox first: `cli_kit.devbox` puts the tool's `.devbox` packages, such as `gh`, first on the PATH, so a command run from `.venv/bin` without starting devbox still runs the programs devbox pins.

Tools also follow these rules, which cli-kit can't enforce:

- Use the standard library first. Add a dependency to a tool's `pyproject.toml` only when it saves real work.
- Make every command safe to re-run: skip each step that's already done.
- Never put a secret on a command line. Read it with `cli_kit.credentials`, and pass it on stdin or in an environment variable.
- Guard a destructive command with typed confirmation (`cli_kit.terminal.ask`) and a separate token with the extra scope. See repo-tools' [Guarding delete](../repo-tools/README.md#guarding-delete).

## Adding a tool

Each tool is its own repository in `~/projects/cli/<tool>`, a uv project in its own devbox. Copy repo-tools for the shape:

1. `devbox.json` with `python@3.13` and `uv`, plus the programs its commands run, and `"UV_PYTHON_DOWNLOADS": "never"`, so uv uses devbox's Python.
2. `pyproject.toml` depending on `cli-kit`, naming its commands under `[project.scripts]`, with its code in `src/<package>/` and its tests in `tests/`. Until cli-kit is on GitHub, take it from its folder: `cli-kit = { path = "../cli-kit" }` under `[tool.uv.sources]`.
3. A `setup.sh` that checks its commands were built and prints the `ln -sf` lines that put them on your PATH, run by `devbox run setup` after `uv sync`.

## Adding a command to a tool

Add a module to the tool's `commands/` with a `register(subparsers)` function, which adds its parser and sets its `run`, and list the module in the tool's `__main__.py`. Its help line comes from `register`. Don't set `formatter_class`: cli-kit gives every command its own, which keeps the description's line breaks.

## Changing cli-kit

cli-kit's behaviour is every tool's behaviour, so change it test-first, and state in its own tests everything a tool relies on: tools aren't where cli-kit's regressions should be caught. Then, in each tool, run `devbox run -- uv sync` to rebuild cli-kit into it and run its tests. Add something to cli-kit only once two tools need it; until then it stays in the tool.

## Development

Once per machine:

```sh
cd ~/projects/cli/cli-kit
devbox run setup   # uv sync, building .venv
```

Then:

```sh
devbox run test    # pytest
devbox run lint    # ruff check and format
```

Tests use `--import-mode=importlib`; share test helpers through fixtures in `conftest.py`, not by importing it.
