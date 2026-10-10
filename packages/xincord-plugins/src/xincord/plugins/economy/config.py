"""The plugin's ``config.yaml``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/config/ConfigSerializer.kt:6-42
"""

from xincord.core.config import Model


class Config(Model):
    """``plugins/Economy/config.yaml``.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin.
    """

    @property
    def admin_id(self) -> tuple[int, ...]:
        """Stub."""
        raise NotImplementedError

    @property
    def board_user_show_limit(self) -> int:
        """Stub."""
        raise NotImplementedError
