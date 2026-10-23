"""Models behind a chat completions API, with the API replaced by a fake urlopen."""

import io
import json
import urllib.error

import pytest

from cli_kit.credentials import Credential, Token
from cli_kit.models import chat_completions
from cli_kit.models.chat_completions import ChatCompletions
from cli_kit.outcome import Precondition

TOKEN = Token(service="test-api-key", name="Test API key", username="email", create="Make one.")


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Server:
    """Answers each request with answer: a dict as JSON, a str as it is, an int as that HTTP
    error, or an exception raised; and records each request."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.answer: object = None
        self.requests: list = []
        self.timeouts: list = []
        monkeypatch.setattr(chat_completions.urllib.request, "urlopen", self.urlopen)

    def urlopen(self, request, timeout):
        self.requests.append(request)
        self.timeouts.append(timeout)
        if isinstance(self.answer, Exception):
            raise self.answer
        if isinstance(self.answer, int):
            raise urllib.error.HTTPError(request.full_url, self.answer, "", {}, io.BytesIO())
        body = self.answer if isinstance(self.answer, str) else json.dumps(self.answer)
        return Response(body.encode())


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch) -> Server:
    monkeypatch.setattr(Token, "read", lambda self: Credential("me@example.com", "secret"))
    return Server(monkeypatch)


@pytest.fixture
def model() -> ChatCompletions:
    return ChatCompletions("https://api.example.com/v1/chat/completions", "small", TOKEN, 30)


def reply_of(text: object) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


def test_the_prompt_is_posted_as_a_user_message_with_the_key_as_bearer(server, model):
    server.answer = reply_of("Sorts socks.")
    assert model.reply("Describe it.") == "Sorts socks."
    [request] = server.requests
    assert request.full_url == "https://api.example.com/v1/chat/completions"
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == "Bearer secret"
    assert json.loads(request.data) == {
        "model": "small",
        "messages": [{"role": "user", "content": "Describe it."}],
    }
    assert server.timeouts == [30]


def test_an_http_error_is_no_reply(server, model):
    server.answer = 429
    assert model.reply("Describe it.") is None


def test_an_unreachable_api_is_no_reply(server, model):
    server.answer = urllib.error.URLError("no route")
    assert model.reply("Describe it.") is None


def test_a_timeout_is_no_reply(server, model):
    server.answer = TimeoutError()
    assert model.reply("Describe it.") is None


def test_an_answer_that_is_not_json_is_no_reply(server, model):
    server.answer = "<html>"
    assert model.reply("Describe it.") is None


def test_an_answer_without_text_is_no_reply(server, model):
    server.answer = {"choices": []}
    assert model.reply("Describe it.") is None
    server.answer = reply_of(None)
    assert model.reply("Describe it.") is None


def test_a_missing_key_stops_before_anything_is_sent(monkeypatch: pytest.MonkeyPatch, model):
    def missing(self):
        raise Precondition("No Test API key is stored.")

    monkeypatch.setattr(Token, "read", missing)
    server = Server(monkeypatch)
    with pytest.raises(Precondition, match="No Test API key"):
        model.reply("Describe it.")
    assert server.requests == []
