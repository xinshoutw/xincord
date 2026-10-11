"""A message's text as the plugin stores it, and the texts that fit an embed field."""

from itertools import accumulate
from typing import TYPE_CHECKING, Protocol

from xincord.plugins.listen_channels.settings import FIELD_MAX, MORE, units

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

# The embeds whose text counts: the ones that bots and webhooks send. None is Discord's default.
# The other types (link, article, image, video, gifv) are previews that Discord adds to a message
# after it is sent, from the links in its content.
RICH = frozenset({"rich", None})


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
    """The text of a message with ``content`` and ``embeds``, as the plugin stores and logs it.

    The content, then each rich embed's text, separated by blank lines; empty parts are left out.
    v3 left the content out when the message had embeds, appended ``null`` for a missing title or
    description, and took every embed, link previews included.
    """
    parts = [content, *(_embed_text(embed) for embed in embeds if embed.type in RICH)]
    return "\n\n".join(part for part in parts if part)


def fit(text: str) -> str:
    """``text`` cut to fit an embed field's value, 1024 UTF-16 code units as JDA counted them.

    A longer text keeps the characters that fit before ``...``: v3 threw there, and the log was
    lost.
    """
    if units(text) <= FIELD_MAX:
        return text
    # The running totals grow, so the characters that fit are the first ones.
    room = FIELD_MAX - units(MORE)
    fitting = sum(1 for total in accumulate(map(units, text)) if total <= room)
    return text[:fitting] + MORE


def _embed_text(embed: EmbedLike) -> str:
    """An embed's text: its author's name and title, its description and its fields.

    The name and the title are on two lines, as each field's name and value; the parts are
    separated by blank lines, as in v3.
    """
    head = "\n".join(part for part in (embed.author.name, embed.title) if part)
    fields = [f"{field.name or ''}\n{field.value or ''}" for field in embed.fields]
    return "\n\n".join(part for part in (head, embed.description, *fields) if part)
