"""The channels and messages that the plugin posts to or archives, as it calls them.

discord.py's ``send`` overloads take a ``View`` or a ``LayoutView``, never their union, which the
rendered templates hold; these Protocols type the calls that the plugin makes. The archive's are
discord.py's text channels, messages, threads and webhooks, as far as it uses them.
"""

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping, Sequence

    import discord


@runtime_checkable
class Guild(Protocol):
    """A guild whose cached channels can be looked up."""

    def get_channel(self, channel_id: int, /) -> object:
        """The cached channel ``channel_id``, or None."""
        ...


def cached_channel(guild: object, text: str) -> object:
    """The channel of the guild's cache whose ID ``text`` is, or None (a text that is no ID too)."""
    return guild.get_channel(int(text)) if text.isdecimal() and isinstance(guild, Guild) else None


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


class Avatar(Protocol):
    """An avatar."""

    @property
    def url(self) -> str:
        """The avatar's URL."""
        ...


class Author(Protocol):
    """A message's author: a member when discord.py has them, else a user."""

    @property
    def id(self) -> int:
        """The user's ID."""
        ...

    @property
    def name(self) -> str:
        """The username."""
        ...

    @property
    def display_name(self) -> str:
        """The name shown: a member's nickname, global name or username."""
        ...

    @property
    def display_avatar(self) -> Avatar:
        """The avatar shown: a member's guild avatar, the user's avatar or the default one."""
        ...


@runtime_checkable
class InGuild(Protocol):
    """An author that discord.py knows as a member of the message's guild."""

    @property
    def guild(self) -> object:
        """The member's guild."""
        ...


class Attachment(Protocol):
    """A message's file."""

    @property
    def size(self) -> int:
        """The file's size in bytes."""
        ...

    @property
    def url(self) -> str:
        """The file's URL."""
        ...

    async def to_file(self) -> discord.File:
        """The file, downloaded, to upload again."""
        ...


class Named(Protocol):
    """A member, as a thread's owner."""

    @property
    def display_name(self) -> str:
        """The name shown."""
        ...


class StartedThread(Protocol):
    """A thread that a message of the ticket started."""

    @property
    def id(self) -> int:
        """The thread's ID, which holds the time it started."""
        ...

    @property
    def name(self) -> str:
        """The thread's name."""
        ...

    @property
    def owner_id(self) -> int:
        """The ID of the member who started it."""
        ...

    @property
    def owner(self) -> Named | None:
        """The member who started it, when discord.py has them."""
        ...

    def history(self, *, limit: int | None, oldest_first: bool) -> AsyncIterator[ArchivedMessage]:
        """The thread's messages."""
        ...


class ArchivedMessage(Protocol):
    """A message of the ticket's history, or of a thread that one started."""

    @property
    def id(self) -> int:
        """The message's ID, which holds the time it was sent."""
        ...

    @property
    def content(self) -> str:
        """The message's text."""
        ...

    @property
    def attachments(self) -> Sequence[Attachment]:
        """The message's files."""
        ...

    @property
    def author(self) -> Author:
        """Who sent the message."""
        ...

    @property
    def thread(self) -> StartedThread | None:
        """The public thread that the message started, if any, from Discord's payload."""
        ...


class History(Protocol):
    """A ticket channel, whose messages the archive copies."""

    @property
    def name(self) -> str:
        """The channel's name."""
        ...

    def history(self, *, limit: int | None, oldest_first: bool) -> AsyncIterator[ArchivedMessage]:
        """The channel's messages."""
        ...


class ArchiveThread(Protocol):
    """The thread that holds an archive."""

    @property
    def id(self) -> int:
        """The thread's ID."""
        ...

    @property
    def mention(self) -> str:
        """The thread's mention."""
        ...

    async def delete(self) -> None:
        """Delete the thread."""
        ...


class Webhook(Protocol):
    """The webhook that posts an archive's messages under their authors' names."""

    async def send(  # noqa: PLR0913 - discord.py's keywords
        self,
        content: str | None = ...,
        *,
        username: str = ...,
        avatar_url: str = ...,
        files: Sequence[discord.File] = ...,
        allowed_mentions: discord.AllowedMentions = ...,
        thread: ArchiveThread = ...,
        wait: bool = ...,
    ) -> object:
        """Send a message to ``thread``."""
        ...

    async def delete(self) -> None:
        """Delete the webhook."""
        ...


class ArchiveTarget(Protocol):
    """The text channel that an archive goes into."""

    async def create_thread(
        self,
        *,
        name: str,
        type: discord.ChannelType,  # noqa: A002 - discord.py's name
    ) -> ArchiveThread:
        """Create a thread without a starter message."""
        ...

    async def create_webhook(self, *, name: str) -> Webhook:
        """Create a webhook in the channel."""
        ...
