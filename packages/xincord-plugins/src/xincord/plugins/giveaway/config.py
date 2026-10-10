"""The plugin's ``config.yaml``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/config/ConfigSerializer.kt:5-10
"""

from typing import TYPE_CHECKING

from xincord.core.config import Model

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo


class Config(Model):
    """``plugins/Giveaway/config.yaml``.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin.
    """

    @property
    def default_locale(self) -> str:
        """The locale whose lang files serve users whose locale has none."""
        raise NotImplementedError

    @property
    def period(self) -> int:
        """Seconds between the automatic draw's passes."""
        raise NotImplementedError

    @property
    def zone(self) -> ZoneInfo | None:
        """The zone of the end times; None for the host's."""
        raise NotImplementedError
