# cli-kit

The framework my command line tools are built on: subcommands, help, exit statuses, running other programs, credentials, terminal prompts and language models. Each tool is its own repository under `~/projects/cli` and depends on cli-kit, so every command behaves the same way.

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

  Usage errors exit 2. ✅ and ➖ go to stdout; the rest to stderr. A command that returns anything else is a bug, and `cli.run` raises. Check preconditions before the first change, so a problem with them is ⚠️, not 🛑. All four come from `cli_kit.outcome`. A standalone command ends the same way by passing its work to `cli.finish`. The scheme is defined in skill-authoring's [skill conventions](https://github.com/ianflanagan1/skill-authoring/blob/main/skill-conventions.md#status-line); cli-kit implements it.
- **Slow steps** say so as they start: `outcome.starting("Waiting for CI")` prints `… Waiting for CI` in grey on stderr, at once, so a long wait isn't silent. It isn't a change, so a 🛑 doesn't list it. Every call to a model or agent does this for you (see [Language models](#language-models)).
- **Choices** are made on the terminal: `terminal.choose(prompt, options)` lists the options under the prompt, the up and down arrows move between them and Enter chooses, and it returns the index of the one chosen. Like `terminal.ask`, it reads the terminal itself, not stdin. With no terminal, as when an agent runs the command, it returns `None` at once, so a command carries on as if nothing was chosen; give the options a way to decline, such as "skip", that the command treats the same. Each line is cut to the terminal's width, ending in `…`, rather than wrapped, so the menu redraws in place in a narrow window; put what tells the options apart at their start. Style the prompt with `terminal.style()`, which colours as `choose` does.
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
2. `pyproject.toml` depending on `cli-kit`, naming its commands under `[project.scripts]`, with its code in `src/<package>/` and its tests in `tests/`. Pin cli-kit to a release tag on GitHub, `cli-kit = { git = "https://github.com/ianflanagan1/cli-kit", tag = "v0.1.0" }` under `[tool.uv.sources]`, never to a branch or a sibling checkout's path, so the tool builds the same way on any machine. Take another tool's library the same way. To release, raise `version` in `pyproject.toml`, commit, then tag it `v<version>` and push the tag; dependants move to it by changing their tag and running `uv lock`.
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

## Repository settings

Settings a repository's team shares, such as where its issues go, are committed in its `.config/` directory, one file for each purpose. [repo-settings](../repo-settings) reads them, from whichever copy each tool says: a worktree's, a branch's or the code host's.

## Language models

A command that asks a model for a reply depends on the `Model` port in `cli_kit.models`, `reply(prompt, purpose) -> str | None`, and is handed an adapter where it's wired, so its tests pass a fake and it never names a vendor:

```python
from cli_kit import models, outcome
from cli_kit.models import Provider

model = models.small(Provider.CLAUDE, outcome.starting)
reply = model.reply(prompt, "Writing a description for me/thing")  # the text, or None
```

Calling a model or an agent is always slow, so none runs silently. Every call names its `purpose`, which has no default, so leaving it out fails the type check; and every adapter is built with an announcer, which it tells the purpose just before the slow part. A command wires `outcome.starting`, so the purpose shows as `… Writing a description for me/thing`; a tool with its own output, such as repo-fix's log under each repository, wires its own.

| Provider | `small()` model | Through |
|---|---|---|
| `claude` | `haiku` | Claude Code run headless (`claude -p`), signed in as you, with no tools, in an empty directory |
| `openai` | `gpt-5-mini` | OpenAI's chat completions API, with the `openai-api-key` credential |
| `gemini` | `gemini-flash-latest` | Gemini's OpenAI-compatible API, with the `gemini-api-key` credential |
| `mistral` | `mistral-small-latest` | Mistral's chat completions API, with the `mistral-api-key` credential |

A missing key stops the command with the ⚠️ that says how to store it (see [Credentials](#credentials)); every other failure, such as a timeout, an HTTP error or `claude` not being installed, is a `None` reply, for the tool to decide what to do without one. Each key is stored once and shared by every tool. A tool that wants another model builds `ClaudeCode(model, timeout_seconds, announce)` or `ChatCompletions(url, model, key, timeout_seconds, announce)` itself from the URLs and keys in `cli_kit.models`. The prompt, and what the tool keeps of the reply, stay in the tool: they're its contract with the model.

A reply sees only the prompt and the model's global context. A command that needs an agent to work in a directory, reading its files and changing them, depends on the `Agent` port instead, `run(prompt, workspace, readable, purpose) -> Finished | Failed | TimedOut`, from `cli_kit.models.agent`:

```python
from cli_kit import outcome
from cli_kit.models.claude_code import ClaudeCode

agent = ClaudeCode(None, 30 * 60, outcome.starting)  # None: the model Claude Code is set to use
ended = agent.run("/ianf-commit", repo, [skill_dir], "Committing with /ianf-commit")
```

`ClaudeCode` runs it as a Claude Code session in `workspace`, with its tools, and `--add-dir` for each readable directory; the prompt is an argument, so a skill's slash command works. `Finished` and `Failed` carry what the agent said, or all it printed when it couldn't say; `TimedOut` comes after `timeout_seconds`, and may have done some of the work. Judge the run by what changed in the workspace, not by what it said: a skill that fails to load still finishes. A Claude Code session started this way loads your own hooks and settings, as any session does.

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
