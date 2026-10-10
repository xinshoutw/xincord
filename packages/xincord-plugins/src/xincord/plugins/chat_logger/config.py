"""The plugin's ``config.yaml``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/config/ConfigSerializer.kt:6-11
"""

from typing import Annotated

from pydantic import Field

from xincord.core.config import Model

# The range of the retention in days. v3 kept every message forever; a bound keeps the stored
# messages from growing without limit.
RETENTION_MIN = 1
RETENTION_MAX = 3650


class Config(Model):
    """``plugins/ChatLogger/config.yaml``: which messages are stored, and for how long.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin.
    """

    # True: the messages of every channel are stored; false: those of the detected channels only.
    log_all: bool = True
    # How many days a message's text is kept; edits and deletions of older messages are not logged.
    retention_days: Annotated[int, Field(ge=RETENTION_MIN, le=RETENTION_MAX)] = 30

    @property
    def max_file_size_mb(self) -> int:
        """The size in MiB from which a new message file starts."""
        raise NotImplementedError
