"""The plugin's ``config.yaml``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/config/ConfigSerializer.kt:6-26
"""

from typing import Annotated

from pydantic import Field, PositiveInt

from xincord.core.config import Model

JAVA_LONG_MAX = 2**63 - 1  # v3's delay was a Long


class Config(Model):
    """``plugins/TicketAwayNotice/config.yaml``: v3's keys, none with a default, as in v3.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin. The
    bundled file holds 0 for both IDs, so the plugin waits for the operator.
    """

    # v3 read the IDs as Strings and refused blank ones; its files hold unquoted 18-digit numbers,
    # and pydantic reads quoted ones too.
    guild_id: PositiveInt  # the guild whose new channels are watched
    user_id: PositiveInt  # the member whose status decides the notice: the shop's owner
    prefix: Annotated[tuple[str, ...], Field(min_length=1)]  # channel name prefixes
    delay_millis: Annotated[int, Field(ge=1, le=JAVA_LONG_MAX)]  # the wait before the notice

    def watches(self, guild_id: int, name: str) -> bool:
        """Whether a new channel named ``name`` in guild ``guild_id`` gets a notice.

        Only ``guild_id`` counts: v3's guild filter never applied (B1). The prefixes compare
        case-sensitively, as Kotlin's ``startsWith``; an empty one matches every name, as in v3.
        """
        return guild_id == self.guild_id and name.startswith(self.prefix)
