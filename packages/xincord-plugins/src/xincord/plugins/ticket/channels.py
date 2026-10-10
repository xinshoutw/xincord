"""The channels and messages that the plugin posts to, as it calls them.

discord.py's ``send`` overloads take a ``View`` or a ``LayoutView``, never their union, which the
rendered templates hold; these Protocols type the calls that the plugin makes.
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
