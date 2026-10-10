"""The plugin's ``config.yaml``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/kotlin/botinfo/config/ConfigSerializer.kt:5-8
"""

from xincord.core.config import Model


class Config(Model):
    """``plugins/BotInfo/config.yaml``; the bundled ``config.yaml`` holds the same defaults.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin.
    """

    @property
    def source_url(self) -> str:
        """Stub until the config has the source link."""
        raise NotImplementedError
