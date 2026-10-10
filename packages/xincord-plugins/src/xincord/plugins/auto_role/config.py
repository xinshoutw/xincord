"""The plugin's ``config.yaml``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/kotlin/autorole/config/ConfigSerializer.kt:6-24
"""

from xincord.core.config import Model


class Config(Model):
    """``plugins/AutoRole/config.yaml``; the bundled ``config.yaml`` holds the same defaults.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin.
    """

    def roles_by_guild(self) -> dict[int, tuple[int, ...]]:
        """Stub until the config lists guilds."""
        raise NotImplementedError
