"""The plugin's ``config.yaml``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/config/ConfigSerializer.kt:5-10
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:93-95
"""

from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord
from pydantic import Field, StrictInt, field_validator

from xincord.core.config import Model

DEFAULT_LOCALE = "zh-TW"  # v3's default locale
# v3's coerceIn(5, 3600) of the automatic draw's period, in seconds.
PERIOD_MIN = 5
PERIOD_MAX = 3600
# The locale tags that JDA's DiscordLocale.from matched exactly, case included.
LOCALES = frozenset(locale.value for locale in discord.Locale)


class Config(Model):
    """``plugins/Giveaway/config.yaml``, with v3's camelCase keys.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin.
    """

    # The locale whose lang files serve users whose locale has none, as v3's fallback.
    default_locale: Annotated[str, Field(alias="defaultLocale")] = DEFAULT_LOCALE
    # Seconds between the automatic draw's passes, clamped by `period` as in v3.
    auto_draw_interval_seconds: Annotated[StrictInt, Field(alias="autoDrawIntervalSeconds")] = 60
    # The IANA zone of the end times; empty for the host's, v3's ZoneId.systemDefault().
    time_zone: Annotated[str, Field(alias="timeZone")] = ""

    @field_validator("default_locale")
    @classmethod
    def _discord_locale(cls, value: str) -> str:
        if value not in LOCALES:
            msg = f"{value} is not a Discord locale"
            raise ValueError(msg)
        return value

    @field_validator("time_zone")
    @classmethod
    def _known_zone(cls, value: str) -> str:
        if value:
            try:
                ZoneInfo(value)
            except (ZoneInfoNotFoundError, ValueError, OSError) as error:
                msg = f"{value} is not a time zone"
                raise ValueError(msg) from error
        return value

    @property
    def period(self) -> int:
        """Seconds between the automatic draw's passes, from 5 to 3600."""
        return max(PERIOD_MIN, min(PERIOD_MAX, self.auto_draw_interval_seconds))

    @property
    def zone(self) -> ZoneInfo | None:
        """The zone of the end times; None for the host's local time."""
        return ZoneInfo(self.time_zone) if self.time_zone else None
