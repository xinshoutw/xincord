"""The plugin's ``config.yaml``: what v3 hard-coded, with v3's values as defaults (decision C1)."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from pydantic import AwareDatetime, ConfigDict, Field, StringConstraints

from xincord.core.config import Model

TAIWAN = timezone(timedelta(hours=8))
# v3 compared LocalDateTime.now() with 2025-12-26 09:00 on the owner's host, in Taiwan.
V3_START = datetime(2025, 12, 26, 9, 0, tzinfo=TAIWAN)
V3_SEMESTER = "1142"
V3_INTERVAL = 1.5  # v3's target cadence, in seconds
MIN_INTERVAL = 1.0  # one request a second at most: the bot cannot hammer NTUST's API
MIN_ALERT_INTERVAL = 10.0
DAY = 86400.0


class Config(Model):
    """``plugins/NtustCourseWatch/config.yaml``, with kebab-case keys as NtustAnnouncements'.

    v3's only key, ``enabled``, is gone: the core config's ``plugins`` list enables the plugin, and
    v3's file loads with every default, which are v3's values.
    """

    # An unquoted semester such as 1151 is a number in YAML; it is read as the text in the file.
    model_config = ConfigDict(coerce_numbers_to_str=True)

    # The semester as NTUST's course query names it: 1151, 1152, 115H (the summer term).
    semester: Annotated[str, StringConstraints(pattern=r"^[0-9A-Za-z]{1,16}$")] = V3_SEMESTER
    # When course selection opens: nothing is asked or posted before. Its offset is required, since
    # the container's local time is UTC.
    start: AwareDatetime = V3_START
    # Seconds from one request to NTUST to the next.
    interval: Annotated[float, Field(ge=MIN_INTERVAL, le=DAY, allow_inf_nan=False)] = V3_INTERVAL
    # Seconds before a channel hears again about a course that still has seats (v3: every poll).
    alert_interval: Annotated[
        float,
        Field(alias="alert-interval", ge=MIN_ALERT_INTERVAL, le=DAY, allow_inf_nan=False),
    ] = 60.0
