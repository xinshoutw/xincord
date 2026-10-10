"""The channels and messages that the plugin posts to and edits, as it calls them.

discord.py's ``send`` and ``edit`` overloads take a ``View`` or a ``LayoutView``, never their union,
which the rendered templates hold; these Protocols type the calls that the plugin makes.
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

    import discord


class Posted(Protocol):
    """A message that the bot sent, as the plugin uses it."""

    @property
    def id(self) -> int:
        """The message's ID."""
        ...

    @property
    def jump_url(self) -> str:
        """The message's link."""
        ...

    async def delete(self) -> None:
        """Delete the message."""
        ...


class Editable(Protocol):
    """A message that the bot can edit without fetching it, as the plugin calls it."""

    async def edit(
        self,
        *,
        content: str | None = None,
        embeds: Sequence[discord.Embed] = (),
        view: discord.ui.View | discord.ui.LayoutView | None = None,
        attachments: Sequence[discord.File] = (),
    ) -> object:
        """Replace the message."""
        ...


@runtime_checkable
class Postable(Protocol):
    """A channel that takes messages (forums and categories do not), as the plugin calls it."""

    async def send(
        self,
        *,
        content: str | None = None,
        embeds: Sequence[discord.Embed] = (),
        view: discord.ui.View | discord.ui.LayoutView | None = None,
        files: Sequence[discord.File] = (),
    ) -> Posted:
        """Send a message to the channel."""
        ...


class Channel(Postable, Protocol):
    """A partial messageable: messages can be sent there and edited by ID."""

    def get_partial_message(self, message_id: int, /) -> Editable:
        """The channel's message ``message_id``, without fetching it."""
        ...


def postable(channel: object) -> Postable | None:
    """``channel`` if it takes messages (forums and categories do not)."""
    return channel if isinstance(channel, Postable) else None
