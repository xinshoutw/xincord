"""The plugin's ``config.yaml``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/config/ConfigSerializer.kt:6-18
"""

from xincord.core.config import Model


class Config(Model):
    """``plugins/Feedbacker/config.yaml``: the plugin's replies.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin.
    """

    @property
    def form_no_permission(self) -> str:
        """Stub until the replies exist."""
        raise NotImplementedError

    @property
    def form_not_you(self) -> str:
        """Stub until the replies exist."""
        raise NotImplementedError

    @property
    def form_success(self) -> str:
        """Stub until the replies exist."""
        raise NotImplementedError

    @property
    def form_failure(self) -> str:
        """Stub until the replies exist."""
        raise NotImplementedError

    @property
    def form_submit_failure(self) -> str:
        """Stub until the replies exist."""
        raise NotImplementedError
