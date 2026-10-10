"""The plugin's ``config.yaml``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/config/ConfigSerializer.kt:5-10
"""

from xincord.core.config import Model


class Config(Model):
    """``plugins/Giveaway/config.yaml``.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin.
    """
