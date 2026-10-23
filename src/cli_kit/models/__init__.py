"""Language models a tool can ask for a reply to a prompt, from whichever provider you choose.

A tool depends on Model, the port, and is handed an adapter where its command is wired:

    model = models.small(Provider.CLAUDE)
    reply = model.reply(prompt)  # the text, or None when the model couldn't give one

The adapters are ClaudeCode, which runs Claude Code headless, signed in as you, and
ChatCompletions, for the OpenAI-style API that OpenAI, Gemini and Mistral each offer, with a key
from the credential store. small() gives each provider's small, cheap model; a tool that needs
another builds the adapter itself, from the URLs and keys here. A key is stored once, under its
provider's name, for every tool.
"""

from enum import StrEnum
from typing import Protocol, assert_never

from cli_kit.credentials import Token
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
    def reply(self, prompt: str) -> str | None:
        """The model's reply to prompt, or None when it couldn't give one."""
        ...


class Provider(StrEnum):
    CLAUDE = "claude"
    OPENAI = "openai"
    GEMINI = "gemini"
    MISTRAL = "mistral"


def small(provider: Provider) -> Model:
    """The provider's small, cheap model, named by an alias that follows its latest where the
    provider has one."""
    match provider:
        case Provider.CLAUDE:
            return ClaudeCode("haiku", TIMEOUT_SECONDS)
        case Provider.OPENAI:
            return ChatCompletions(OPENAI_URL, "gpt-5-mini", OPENAI_KEY, TIMEOUT_SECONDS)
        case Provider.GEMINI:
            return ChatCompletions(GEMINI_URL, "gemini-flash-latest", GEMINI_KEY, TIMEOUT_SECONDS)
        case Provider.MISTRAL:
            return ChatCompletions(
                MISTRAL_URL, "mistral-small-latest", MISTRAL_KEY, TIMEOUT_SECONDS
            )
        case _:
            assert_never(provider)
