"""The plugin's ``config.yaml``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/config/ConfigSerializer.kt:5-15
"""

from xincord.core.config import Model


class Config(Model):
    """``plugins/IntervalPusher/config.yaml``; the bundled ``config.yaml`` lists no listeners.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin.
    """
