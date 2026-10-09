"""The plugin's ``config.yaml``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/_Example/src/main/kotlin/_example/config/ConfigSerializer.kt:6-12
"""

from xincord.core.config import Model


class Config(Model):
    """``plugins/_Example/config.yaml``; the bundled ``config.yaml`` holds the same defaults."""

    @property
    def example_key(self) -> str:
        """Stub until the field exists."""
        raise NotImplementedError
