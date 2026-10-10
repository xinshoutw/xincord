"""Each guild's listen channel settings, kept in the shared store as v3's documents.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/JsonManager.kt:17-117
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/json/JsonData.kt:5-15
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-40
"""

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable

    from xincord.core.storage import Store

    from .settings import Setting

NAMESPACE = "VoiceLogger"  # the plugin's name; keys are guild IDs

type Kind = Literal["allow", "block"]


class DataError(Exception):
    """A stored document is not of v3's shape; it is left as it is."""


async def read_settings(store: Store, guild_id: int) -> dict[int, Setting]:
    """Return the guild's settings by listen channel ID, in stored order, and write nothing.

    Raises:
        NotImplementedError: Not implemented yet.
    """
    raise NotImplementedError


async def read_setting(store: Store, guild_id: int, channel_id: int) -> Setting:
    """Return the settings of listen channel ``channel_id``, and write nothing.

    Raises:
        NotImplementedError: Not implemented yet.
    """
    raise NotImplementedError


async def toggle(store: Store, guild_id: int, channel_id: int) -> Setting:
    """Switch the listen channel between the allow and the block mode; return its settings.

    Raises:
        NotImplementedError: Not implemented yet.
    """
    raise NotImplementedError


async def add_channels(
    store: Store, guild_id: int, channel_id: int, kind: Kind, ids: Iterable[int]
) -> Setting:
    """Add ``ids`` to the listen channel's ``kind`` list; return its settings.

    Raises:
        NotImplementedError: Not implemented yet.
    """
    raise NotImplementedError


async def remove(store: Store, guild_id: int, channel_id: int) -> bool:
    """Delete the listen channel's settings; return whether it had some.

    Raises:
        NotImplementedError: Not implemented yet.
    """
    raise NotImplementedError
