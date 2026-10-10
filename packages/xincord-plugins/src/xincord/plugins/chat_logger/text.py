"""A message's text as the plugin stores it, and the texts that fit an embed field.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/ChatLogger.kt:298-317
"""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence


class FieldLike(Protocol):
    """An embed field."""

    @property
    def name(self) -> str | None:
        """The field's name."""
        ...

    @property
    def value(self) -> str | None:
        """The field's value."""
        ...


class AuthorLike(Protocol):
    """An embed's author."""

    @property
    def name(self) -> str | None:
        """The author's name, if the embed has one."""
        ...


class EmbedLike(Protocol):
    """An embed of a message, as discord.py's ``Embed`` holds it."""

    @property
    def type(self) -> str | None:
        """Discord's embed type: ``rich`` for the embeds that bots and webhooks send."""
        ...

    @property
    def author(self) -> AuthorLike:
        """The embed's author."""
        ...

    @property
    def title(self) -> str | None:
        """The embed's title."""
        ...

    @property
    def description(self) -> str | None:
        """The embed's description."""
        ...

    @property
    def fields(self) -> Sequence[FieldLike]:
        """The embed's fields."""
        ...


def message_text(content: str, embeds: Iterable[EmbedLike]) -> str:
    """The text of a message with ``content`` and ``embeds``, as the plugin stores and logs it."""
    raise NotImplementedError


def fit(text: str) -> str:
    """``text`` cut to fit an embed field's value."""
    raise NotImplementedError
