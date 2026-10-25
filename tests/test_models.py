from cli_kit.models import GEMINI_KEY, MISTRAL_KEY, OPENAI_KEY, Provider, small
from cli_kit.models.chat_completions import ChatCompletions
from cli_kit.models.claude_code import ClaudeCode
from cli_kit.outcome import starting


def test_claudes_small_model_is_haiku_through_claude_code():
    assert small(Provider.CLAUDE, starting) == ClaudeCode("haiku", 120, starting)


def test_the_other_providers_small_models_are_reached_through_their_chat_completions_apis():
    assert small(Provider.OPENAI, starting) == ChatCompletions(
        "https://api.openai.com/v1/chat/completions", "gpt-5-mini", OPENAI_KEY, 120, starting
    )
    assert small(Provider.GEMINI, starting) == ChatCompletions(
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "gemini-flash-latest",
        GEMINI_KEY,
        120,
        starting,
    )
    assert small(Provider.MISTRAL, starting) == ChatCompletions(
        "https://api.mistral.ai/v1/chat/completions",
        "mistral-small-latest",
        MISTRAL_KEY,
        120,
        starting,
    )


def test_each_providers_key_is_stored_under_its_own_name():
    services = {OPENAI_KEY.service, GEMINI_KEY.service, MISTRAL_KEY.service}
    assert services == {"openai-api-key", "gemini-api-key", "mistral-api-key"}
