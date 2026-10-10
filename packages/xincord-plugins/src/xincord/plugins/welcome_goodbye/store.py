"""Each guild's welcome and bye channels, kept in the shared store as v3's documents.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/WelcomeByeGuild.kt:25-43
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-41
"""

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from xincord.core.storage import JSON, Store

type Kind = Literal["welcome", "bye"]

KINDS: tuple[Kind, ...] = ("welcome", "bye")

NAMESPACE = "WelcomeGoodbye"  # the store namespace: the plugin's name, keys are guild IDs
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
    """Return the guild's bindings without writing; a guild without a document has none.

    A missing field reads as unbound and other fields are ignored, as v3's Moshi adapter did.
    """
    document = await store.get(NAMESPACE, str(guild_id))
    fields = document if isinstance(document, dict) else {}
    return Bindings(
        welcome=_channel_id(fields.get(FIELDS["welcome"])),
        bye=_channel_id(fields.get(FIELDS["bye"])),
    )


async def set_channel(
    store: Store, guild_id: int, kind: Kind, channel_id: int
) -> tuple[Bindings, int]:
    """Bind ``channel_id`` as the guild's ``kind`` channel, or unbind it with 0.

    Returns the bindings afterwards and the channel bound before; nothing is written when the
    channel does not change. The guild's lock keeps concurrent changes from losing one another:
    discord.py runs handlers concurrently, where v3 had one JDA event thread.
    """
    async with store.lock(f"{NAMESPACE}:{guild_id}"):
        bindings = await read(store, guild_id)
        previous = bindings.channel(kind)
        if previous != channel_id:
            bindings = replace(bindings, **{kind: channel_id})
            await store.put(NAMESPACE, str(guild_id), _document(bindings))
        return bindings, previous


async def forget(store: Store, guild_id: int) -> None:
    """Delete the guild's bindings, as v3 deleted its data file."""
    await store.delete(NAMESPACE, str(guild_id))


async def guild_ids(store: Store) -> list[int]:
    """Return the guilds that have stored bindings."""
    return [int(key) for key in await store.keys(NAMESPACE)]


def _channel_id(value: JSON) -> int:
    """A stored channel ID; anything else, a missing field included, is unbound."""
    return value if isinstance(value, int) else 0


def _document(bindings: Bindings) -> dict[str, JSON]:
    """v3's ``GuildSetting`` document, which a migration of v3's files can copy as it is."""
    return {FIELDS["welcome"]: bindings.welcome, FIELDS["bye"]: bindings.bye}
