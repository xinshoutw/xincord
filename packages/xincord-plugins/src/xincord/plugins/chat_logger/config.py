"""The plugin's ``config.yaml``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/config/ConfigSerializer.kt:6-11
"""

from xincord.core.config import Model


class Config(Model):
    """``plugins/ChatLogger/config.yaml``: which messages are stored.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin.
    """

    # True: the messages of every channel are stored; false: those of the detected channels only.
    log_all: bool = True
