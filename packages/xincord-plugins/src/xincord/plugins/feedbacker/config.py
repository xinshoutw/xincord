"""The plugin's ``config.yaml``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/config/ConfigSerializer.kt:6-18
"""

from xincord.core.config import Model


class Config(Model):
    """``plugins/Feedbacker/config.yaml``: the plugin's replies.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin.
    """
