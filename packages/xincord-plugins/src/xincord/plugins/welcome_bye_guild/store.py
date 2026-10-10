"""Each guild's welcome and bye channels, kept in the shared store as v3's documents.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/WelcomeByeGuild.kt:25-43
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-41
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from xincord.core.storage import Store

type Kind = Literal["welcome", "bye"]

NAMESPACE = "WelcomeByeGuild"  # the store namespace: the plugin's name, keys are guild IDs
# v3's GuildSetting fields, the keys of its plugins/WelcomeByeGuild/data/<guildId>.json files.
FIELDS: dict[Kind, str] = {"welcome": "welcomeChannelId", "bye": "byeChannelId"}


@dataclass(frozen=True)
class Bindings:
    """A guild's welcome and bye channel IDs; 0 when a channel is unbound, as in v3."""

    welcome: int = 0
    bye: int = 0

    def channel(self, kind: Kind) -> int:
        """The channel ID bound for ``kind``."""
        return self.welcome if kind == "welcome" else self.bye


async def read(store: Store, guild_id: int) -> Bindings:
    """Stub until the bindings are stored."""
    raise NotImplementedError


async def set_channel(
    store: Store, guild_id: int, kind: Kind, channel_id: int
) -> tuple[Bindings, int]:
    """Stub until the bindings are stored."""
    raise NotImplementedError


async def forget(store: Store, guild_id: int) -> None:
    """Stub until the bindings are stored."""
    raise NotImplementedError


async def guild_ids(store: Store) -> list[int]:
    """Stub until the bindings are stored."""
    raise NotImplementedError
