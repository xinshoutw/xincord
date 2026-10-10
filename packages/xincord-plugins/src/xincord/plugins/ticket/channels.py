"""The channels and messages that the plugin posts to, as it calls them.

discord.py's ``send`` overloads take a ``View`` or a ``LayoutView``, never their union, which the
rendered templates hold; these Protocols type the calls that the plugin makes.
"""

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    import discord


class Posted(Protocol):
    """A message that the bot sent, as the plugin uses it."""

    @property
    def id(self) -> int:
        """The message's ID."""
        ...

    async def delete(self) -> None:
        """Delete the message."""
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


class TicketChannel(Protocol):
    """A ticket's text channel, as the plugin calls it."""

    @property
    def id(self) -> int:
        """The channel's ID."""
        ...

    @property
    def mention(self) -> str:
        """The channel's mention."""
        ...

    async def send(
        self,
        *,
        content: str,
        allowed_mentions: discord.AllowedMentions,
        view: discord.ui.View = ...,
    ) -> object:
        """Send a message to the channel."""
        ...

    async def delete(self) -> None:
        """Delete the channel."""
        ...


class Category(Protocol):
    """A category that the plugin creates ticket channels in."""

    @property
    def overwrites(self) -> Mapping[Any, discord.PermissionOverwrite]:
        """The category's permission overwrites by role or member."""
        ...

    def permissions_for(self, obj: Any, /) -> discord.Permissions:  # noqa: ANN401 - discord.py's
        """The permissions that ``obj`` has in the category."""
        ...

    async def create_text_channel(
        self, name: str, *, overwrites: Mapping[Any, discord.PermissionOverwrite]
    ) -> TicketChannel:
        """Create a text channel in the category."""
        ...
