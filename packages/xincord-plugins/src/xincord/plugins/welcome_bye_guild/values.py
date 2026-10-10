"""v3's ``wbg@`` placeholders for the replies and the welcome and bye messages.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/WelcomeByeGuildSubstitutorFactory.kt:12-113
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/WelcomeByeGuild.kt:276-284
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from xincord.core.placeholders import GuildLike

if TYPE_CHECKING:
    import discord

    from xincord.core.placeholders import UserLike

    from .store import Bindings

PREFIX = "wbg@"  # v3's prefix of the plugin's keys
NONE = "-"  # v3's text for a missing value


@runtime_checkable
class TextChannelLike(Protocol):
    """A guild channel as the placeholders read it; its type tells text channels apart."""

    @property
    def id(self) -> int:
        """The channel ID."""
        ...

    @property
    def name(self) -> str:
        """The channel name."""
        ...

    @property
    def mention(self) -> str:
        """The mention markup."""
        ...

    @property
    def type(self) -> discord.ChannelType:
        """The channel type."""
        ...


class GuildChannels(GuildLike, Protocol):
    """A guild as the placeholders read it, with its cached channels; ``discord.Guild`` is one."""

    def get_channel(self, channel_id: int, /) -> object:
        """The cached channel with that ID, if any."""
        ...


def text_channel(channel: object) -> TextChannelLike | None:
    """Stub until the placeholders exist."""
    raise NotImplementedError


def command_values(
    interaction: discord.Interaction,
    guild: GuildChannels,
    bindings: Bindings,
    *,
    selected: TextChannelLike | None = None,
    previous: int = 0,
) -> dict[str, str]:
    """Stub until the placeholders exist."""
    raise NotImplementedError


def member_event_values(
    bot: UserLike | None,
    user: UserLike,
    guild: GuildChannels,
    bindings: Bindings,
    event_type: str,
) -> dict[str, str]:
    """Stub until the placeholders exist."""
    raise NotImplementedError
