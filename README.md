# cli-kit

The framework my command line tools are built on: subcommands, help, exit statuses, running other programs, credentials and terminal prompts. Each tool is its own repository under `~/projects/cli` and depends on cli-kit, so every command behaves the same way.

| Tool | Commands | What for |
|---|---|---|
| [repo-tools](../repo-tools) | `github`, `bitbucket`, `packagist`, `repo-list`, `repo-fix` | Publishing repos on GitHub, Bitbucket and Packagist, reading their delivery data, and reporting and fixing the state of every repo under `~/projects` |
| [mem-tools](../mem-tools) | `mem` | Seeing how close a development machine is to running out of memory, what's using it by app and by project, and what's safe to stop |
| [jira-tools](../jira-tools) | `jira` | Filing Jira issues, with where they were raised, and reading, starting, moving, assigning and commenting on them; and a Claude Code skill that files them |
| [product-map](../product-map) | `product-map` | Building a product map of an app from its code, for colleagues reporting problems with it, and publishing it to the report-problem plugin |

## How every command behaves

cli-kit gives every tool built on `cli_kit.cli.run`:

- **Help:** `<tool> help`, `-h`, `--help`, or no command at all, lists the commands with their arguments. `<tool> help <command>` or `<tool> <command> --help` shows one command in full. Placeholders are in angle brackets and a fixed set of values is written as alternatives, `release <dir> patch|minor|major`, so what you type reads differently from what you fill in. On a terminal, headings and command names are bold, command summaries grey, options cyan and placeholders yellow; `NO_COLOR` turns colour off and `FORCE_COLOR` keeps it when piping. A standalone command such as repo-list gets the same by building its parser with `cli.ArgumentParser`. For colour in a command's own output, make a `colour.Style.for_stream(sys.stdout)` and style text with it.
- **Outcomes:** every command ends with one status line, in the same scheme as my skills:

  | Line | Outcome | A command… | Exit |
  |---|---|---|---|
  | `✅ Published.` and the result, such as a URL | it changed state as asked | returns `Done(summary, *details)` | 0 |
  | `➖ Already archived.` | there was nothing to do | returns `NothingToDo(summary)` | 0 |
  | `⚠️ Uncommitted changes in …` | something it needs isn't so, so it tried nothing | raises `Precondition(message, *details)` | 1 |
  | `❌ Publish failed.` and the error | a step ran and failed | raises `Failure(message, *details)` | 1 |
  | `🛑 Stopped.`, what was done, the error, how to resume | either problem, after it had changed something | calls `outcome.changed(...)` for each change | 1 |

  Usage errors exit 2. ✅ and ➖ go to stdout; the rest to stderr. A command that returns anything else is a bug, and `cli.run` raises. Check preconditions before the first change, so a problem with them is ⚠️, not 🛑. All four come from `cli_kit.outcome`. A standalone command ends the same way by passing its work to `cli.finish`. The scheme is defined in the improve-skill plugin's [skill conventions](https://github.com/ianflanagan1/claude-improve-skill/blob/main/skills/improve-skill/references/skill-conventions.md#status-line); cli-kit implements it.
- **Any other exception** is a bug, and shows a traceback.
- **Programs it runs** come from the tool's devbox first: `cli_kit.devbox` puts the tool's `.devbox` packages, such as `gh`, first on the PATH, so a command run from `.venv/bin` without starting devbox still runs the programs devbox pins.

Tools also follow these rules, which cli-kit can't enforce:

- Run on macOS and Linux, every feature on both.
- Use the standard library first. Add a dependency to a tool's `pyproject.toml` only when it saves real work.
- Make every command safe to re-run: skip each step that's already done.
- Never put a secret on a command line. Declare it as a `credentials.Token` and read it from that (see [Credentials](#credentials)), and pass it on stdin or in an environment variable.
- Guard a destructive command with typed confirmation (`cli_kit.terminal.ask`) and a separate token with the extra scope. See repo-tools' [Guarding delete](../repo-tools/README.md#guarding-delete).

## Adding a tool

Each tool is its own repository in `~/projects/cli/<tool>`, a uv project in its own devbox. Copy repo-tools for the shape:

1. `devbox.json` with `python@3.13` and `uv`, plus the programs its commands run, and `"UV_PYTHON_DOWNLOADS": "never"`, so uv uses devbox's Python.
2. `pyproject.toml` depending on `cli-kit`, naming its commands under `[project.scripts]`, with its code in `src/<package>/` and its tests in `tests/`. Take cli-kit from its main branch on GitHub: `cli-kit = { git = "https://github.com/ianflanagan1/cli-kit", branch = "main" }` under `[tool.uv.sources]`.
3. A `setup.sh`, run by `devbox run setup` after `uv sync`, that ends with `"$here/.venv/bin/python" -m cli_kit.link "$here"`. That links each command in `[project.scripts]` from `.venv/bin` into `~/.local/bin`, or `$XDG_BIN_HOME`, checking all of them first. It skips links already in place, replaces ones left dangling by a moved checkout, and never replaces a command of the same name from elsewhere.

## Adding a command to a tool

Add a module to the tool's `commands/` with a `register(subparsers: cli.Subparsers)` function, which adds its parser and sets its `run`, and list the module in the tool's `__main__.py`. Its help line comes from `register`. Don't set `formatter_class`: cli-kit gives every command its own, which keeps the description's line breaks.

## Credentials

A tool declares each token it needs once, as a module constant beside the code that uses it, and reads it there:

```python
from cli_kit.credentials import Token

DELETE_TOKEN = Token(
    service="github-delete-repo-token",
    name="GitHub delete_repo token",
    username="github-username",
    create="Create a classic token with only the delete_repo scope at https://github.com/settings/tokens.",
    confirm_each_read=True,
)

token = DELETE_TOKEN.read().token
```

cli-kit reads it from the macOS keychain or, on Linux, the Secret Service keyring. When it isn't stored, the command stops with a ⚠️ that says how to create it and gives the command that stores it on that system:

```
⚠️ No GitHub delete_repo token is stored.
Create a classic token with only the delete_repo scope at https://github.com/settings/tokens.
Then store it, pasting it at the prompt:
  printf 'Token: '; read -rs token; echo
  printf 'add-generic-password -a <github-username> -s github-delete-repo-token -T "" -w %s\n' "$token" | security -i; unset token
macOS will ask for your login password each time it's read: choose Allow, never Always Allow.
```

On macOS the token goes to `security -i` on stdin, not through `security add-generic-password -w`'s own prompt, which keeps only the first 128 characters of what you paste. Atlassian's API tokens have 192.

So a tool's README needn't repeat the commands: it says which tokens there are and why, and the commands say how to store them. Set `confirm_each_read` for a token that can do lasting harm; the keychain then asks for your login password on each read. On Linux the keyring has no such check.

## Changing cli-kit

cli-kit's behaviour is every tool's behaviour, so change it test-first, and state in its own tests everything a tool relies on: tools aren't where cli-kit's regressions should be caught. Push it, then update each tool to it and run the tool's tests. Add something to cli-kit only once two tools need it; until then it stays in the tool.

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
