"""The plugin's ``config.yaml``."""

from xincord.core.config import Model


class Config(Model):
    """``plugins/Example/config.yaml``; the bundled ``config.yaml`` holds the same defaults.

    The core config's ``plugins`` list enables the plugin; an ``enabled`` key here only warns.
    """

    example_key: str = "example_value"  # shown in the reply as %example@example_key%
