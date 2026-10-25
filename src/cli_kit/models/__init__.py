"""Language models a tool can ask for a reply to a prompt, from whichever provider you choose,
and agents it can have do work in a workspace.

A tool depends on Model, the port, and is handed an adapter where its command is wired:

    model = models.small(Provider.CLAUDE, outcome.starting)
    reply = model.reply(prompt, "Writing a description for me/thing")  # the text, or None

Every call names its purpose, and the adapter announces it, with the announcer it was wired
with, before the slow part: so no call to a model or agent runs silently, and the line says what
it's for wherever the command's output goes.

The adapters are ClaudeCode, which runs Claude Code headless, signed in as you, and
ChatCompletions, for the OpenAI-style API that OpenAI, Gemini and Mistral each offer, with a key
from the credential store. small() gives each provider's small, cheap model; a tool that needs
another builds the adapter itself, from the URLs and keys here. A key is stored once, under its
provider's name, for every tool.

A reply sees only the prompt and the model's global context. An agent runs a session in a
workspace, where it can read its files and change them; a tool depends on Agent for that, from
cli_kit.models.agent, which ClaudeCode implements too:

    agent = ClaudeCode(None, timeout_seconds, outcome.starting)
    ended = agent.run(prompt, workspace, readable, purpose)  # Finished, Failed or TimedOut
"""

from enum import StrEnum
from typing import Protocol, assert_never

from cli_kit.credentials import Token
from cli_kit.models.agent import Announce
from cli_kit.models.chat_completions import ChatCompletions
from cli_kit.models.claude_code import ClaudeCode

TIMEOUT_SECONDS = 120

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

OPENAI_KEY = Token(
    service="openai-api-key",
    name="OpenAI API key",
    username="openai-email",
    create="Create an API key at https://platform.openai.com/api-keys.",
)
GEMINI_KEY = Token(
    service="gemini-api-key",
    name="Gemini API key",
    username="google-email",
    create="Create an API key at https://aistudio.google.com/apikey.",
)
MISTRAL_KEY = Token(
    service="mistral-api-key",
    name="Mistral API key",
    username="mistral-email",
    create="Create an API key at https://console.mistral.ai/api-keys.",
)


class Model(Protocol):
    def reply(self, prompt: str, purpose: str) -> str | None:
        """The model's reply to prompt, or None when it couldn't give one. Announces purpose
        first, such as "Writing a description for me/thing"."""
        ...


class Provider(StrEnum):
    CLAUDE = "claude"
    OPENAI = "openai"
    GEMINI = "gemini"
    MISTRAL = "mistral"


def small(provider: Provider, announce: Announce) -> Model:
    """The provider's small, cheap model, named by an alias that follows its latest where the
    provider has one, announcing each call's purpose with announce."""
    match provider:
        case Provider.CLAUDE:
            return ClaudeCode("haiku", TIMEOUT_SECONDS, announce)
        case Provider.OPENAI:
            return ChatCompletions(OPENAI_URL, "gpt-5-mini", OPENAI_KEY, TIMEOUT_SECONDS, announce)
        case Provider.GEMINI:
            return ChatCompletions(
                GEMINI_URL, "gemini-flash-latest", GEMINI_KEY, TIMEOUT_SECONDS, announce
            )
        case Provider.MISTRAL:
            return ChatCompletions(
                MISTRAL_URL, "mistral-small-latest", MISTRAL_KEY, TIMEOUT_SECONDS, announce
            )
        case _:
            assert_never(provider)
