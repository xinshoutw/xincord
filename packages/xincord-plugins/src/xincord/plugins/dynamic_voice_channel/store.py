"""Each guild's bindings and rooms, kept in the shared store.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/JsonManager.kt:30-142
    XsDiscordBotKt@3a59607:Plugins/DynamicVoiceChannel/src/main/kotlin/dynamicvoicechannel/json/JsonData.kt:3-29
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/json/JsonGuildFileManager.kt:7-40
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable

    from xincord.core.storage import Store

NAMESPACE = "DynamicVoiceChannel"  # the bindings: the plugin's name, keys are guild IDs

type Key = tuple[int, str]  # a binding's category ID and lobby name, v3's DataContainer identity


class DataError(Exception):
    """A stored document is not of the expected shape; it is left as it is."""


@dataclass(frozen=True)
class Binding:
    """v3's ``DataContainer``: a lobby, by its category and exact name, and the room formats."""

    category_id: int
    default_name: str
    format_name_1: str = ""
    format_name_2: str = ""  # stored and never used, as in v3

    @property
    def key(self) -> Key:
        """The category and the lobby name, which identify a binding."""
        return (self.category_id, self.default_name)


async def read_bindings(store: Store, guild_id: int) -> list[Binding]:
    """Return the guild's bindings in the stored order, and write nothing."""
    raise NotImplementedError


def find(bindings: Iterable[Binding], category_id: int, name: str) -> Binding | None:
    """Return the first binding of ``category_id`` whose lobby name is exactly ``name``."""
    raise NotImplementedError


async def bind(store: Store, guild_id: int, binding: Binding) -> None:
    """Store ``binding`` in place of those with the same category and lobby name."""
    raise NotImplementedError


async def unbind(store: Store, guild_id: int, category_id: int, name: str) -> bool:
    """Remove the bindings of ``category_id`` and ``name``; return whether there was one."""
    raise NotImplementedError


async def drop(store: Store, guild_id: int, keys: Collection[Key]) -> None:
    """Remove the bindings whose category and lobby name are in ``keys``."""
    raise NotImplementedError
