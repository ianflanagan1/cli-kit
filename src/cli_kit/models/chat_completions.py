"""Models behind an OpenAI-style chat completions API, which OpenAI, Google's Gemini and
Mistral each offer, with an API key from the system credential store."""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from cli_kit.credentials import Token


@dataclass(frozen=True)
class ChatCompletions:
    url: str
    model: str
    key: Token
    timeout_seconds: float

    def reply(self, prompt: str) -> str | None:
        """Raises Precondition, saying how to store it, when the key isn't stored."""
        key = self.key.read().token
        request = urllib.request.Request(
            self.url,
            data=json.dumps(
                {"model": self.model, "messages": [{"role": "user", "content": prompt}]}
            ).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                answer = json.load(response)
            text = answer["choices"][0]["message"]["content"]
        except (urllib.error.URLError, TimeoutError, ValueError, LookupError, TypeError):
            return None
        return text if isinstance(text, str) else None
