"""The model's API: each format's request and its answer's text.

``gemini`` is v3's API, Gemini's ``generateContent``; ``openai`` is the chat completions API that
OpenAI, OpenRouter, Ollama and Gemini itself offer. Both are plain REST calls over the plugin's
aiohttp session (``web.Web.generate``), with ``config.yaml``'s model settings.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/service/GeminiApiService.kt:34-36
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/service/GeminiApiService.kt:131-150
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from .strings import trim

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta"  # Gemini's REST API
GEMINI_MODEL = "gemini-2.5-flash"  # v3's model
TEMPERATURE = 0.1  # v3's generation config
REQUEST_TIMEOUT = 300.0  # seconds that an attempt may take; v3's SDK set none
CONNECT_TIMEOUT = 30.0  # seconds to connect


class ApiFormat(StrEnum):
    """How an attempt asks the model and how its answer reads."""

    GEMINI = "gemini"  # Gemini's generateContent, the key in x-goog-api-key (v3's API)
    OPENAI = "openai"  # an OpenAI-compatible chat/completions, the key as a bearer token


class ApiError(Exception):
    """The model's API answered an attempt with a status other than 200."""

    def __init__(self, status: int, message: str) -> None:
        """Keep the status and the API's error message, if any."""
        super().__init__(f"code {status}: {message}" if message else f"code {status}")
        self.status = status


@dataclass(frozen=True)
class Api:
    """How each attempt is made: ``config.yaml``'s model settings, v3's values by default."""

    format: ApiFormat = ApiFormat.GEMINI
    endpoint: str = GEMINI_ENDPOINT  # the API's base URL with its version, no final slash
    model: str = GEMINI_MODEL
    temperature: float | None = TEMPERATURE  # None sends none: the API's default
    max_output_tokens: int | None = None  # None sends none: the API's default
    request_timeout: float = REQUEST_TIMEOUT
    connect_timeout: float = CONNECT_TIMEOUT

    @property
    def url(self) -> str:
        """Where each attempt is posted: the endpoint and the format's path."""
        if self.format is ApiFormat.OPENAI:
            return f"{self.endpoint}/chat/completions"
        return f"{self.endpoint}/models/{self.model}:generateContent"

    def headers(self, key: str) -> dict[str, str]:
        """The header that carries ``key``: never the URL."""
        if self.format is ApiFormat.OPENAI:
            return {"Authorization": f"Bearer {key}"}
        return {"x-goog-api-key": key}

    def body(self, prompt: str) -> dict[str, object]:
        """The request's JSON body: the prompt and the generation settings that are not None.

        ``gemini``: the prompt as the only text part, the settings in ``generationConfig``, left
        out when both are None. ``openai``: the prompt as the only user message, as it was
        Gemini's only part; ``max_tokens``, which Ollama, OpenRouter and Gemini's compatible
        endpoint take, rather than OpenAI's newer ``max_completion_tokens``.
        """
        if self.format is ApiFormat.OPENAI:
            chat: dict[str, object] = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
            }
            return chat | _settings(temperature=self.temperature, max_tokens=self.max_output_tokens)
        contents: dict[str, object] = {"contents": [{"parts": [{"text": prompt}]}]}
        config = _settings(temperature=self.temperature, maxOutputTokens=self.max_output_tokens)
        return contents | {"generationConfig": config} if config else contents


def _settings(**settings: float | None) -> dict[str, object]:
    """The settings that are not None: the others are left to the API."""
    return {name: value for name, value in settings.items() if value is not None}


def _field(value: object, name: str) -> object:
    """``value[name]`` when ``value`` is a JSON object, else None."""
    return cast("dict[str, object]", value).get(name) if isinstance(value, dict) else None


def _items(value: object) -> list[object]:
    """``value`` when it is a JSON array, else no items."""
    return cast("list[object]", value) if isinstance(value, list) else []


def answer_text(api_format: ApiFormat, answer: object) -> str:
    """The text of an answer in ``api_format``, trimmed.

    ``gemini``: the first candidate's text parts, joined (v3's ``callOnce``). ``openai``: the first
    choice's message content, when it is a string. An answer without them (a blocked prompt, a
    refusal, a tool call) gives an empty text, a failed attempt.
    """
    if api_format is ApiFormat.OPENAI:
        choices = _items(_field(answer, "choices"))
        content = _field(_field(choices[0], "message"), "content") if choices else None
        return trim(content) if isinstance(content, str) else ""
    candidates = _items(_field(answer, "candidates"))
    if not candidates:
        return ""
    parts = _items(_field(_field(candidates[0], "content"), "parts"))
    texts = [text for part in parts if isinstance(text := _field(part, "text"), str)]
    return trim("".join(texts))


def error_message(answer: object) -> str:
    """The ``error.message`` of an error answer, which both formats' APIs give; else empty."""
    message = _field(_field(answer, "error"), "message")
    return message if isinstance(message, str) else ""
