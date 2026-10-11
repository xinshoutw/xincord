"""The plugin's ``config.yaml``."""

from typing import Annotated

from pydantic import Field

from xincord.core.config import Model

# The range of the retention in days. v3 kept every message forever; a bound keeps the stored
# messages from growing without limit. The owner's default (2026-10-10) is 5 years of 365.25 days.
RETENTION_MIN = 1
RETENTION_MAX = 3650
RETENTION_DEFAULT = 1826
# The size in MiB from which a new message file starts. The upper bound refuses a size in bytes.
FILE_SIZE_MAX = 65536
FILE_SIZE_DEFAULT = 256


class Config(Model):
    """``plugins/ChatLogger/config.yaml``: which messages are stored, how long, and in what files.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin.
    """

    # True: the messages of every channel are stored; false: those of the detected channels only.
    log_all: bool = True
    # How many days a message's text is kept; edits and deletions of older messages are not logged.
    retention_days: Annotated[int, Field(ge=RETENTION_MIN, le=RETENTION_MAX)] = RETENTION_DEFAULT
    # True: a deleted message stays stored until the retention removes it, as v3 kept it.
    keep_deleted: bool = False
    # When the newest message file reaches this size in MiB, a new file starts.
    max_file_size_mb: Annotated[int, Field(ge=1, le=FILE_SIZE_MAX)] = FILE_SIZE_DEFAULT
