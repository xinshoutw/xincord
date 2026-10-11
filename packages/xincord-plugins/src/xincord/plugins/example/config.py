"""The plugin's ``config.yaml``."""

from xincord.core.config import Model


class Config(Model):
    """``plugins/Example/config.yaml``; the bundled ``config.yaml`` holds the same defaults.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin.
    """

    example_key: str = "example_value"  # shown in the reply as %_Example@example_key%
