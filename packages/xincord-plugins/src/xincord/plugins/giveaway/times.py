"""End times as administrators type and see them: ``yyyy-MM-dd HH:mm`` in the configured zone."""

import calendar
import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import tzinfo

# Java's ofPattern("yyyy-MM-dd HH:mm") in its strict parse: ASCII digits, a four-digit year
# without a sign (years past 9999 needed one), two-digit fields.
PATTERN = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2}) ([0-9]{2}):([0-9]{2})")
LAST_MONTH, LAST_DAY, LAST_HOUR, LAST_MINUTE = 12, 31, 23, 59
END_OF_DAY = 24  # 24:00, which Java's SMART resolver reads as the next day's start


def parse_end_time(text: str, zone: tzinfo | None) -> int | None:
    """The epoch second of ``text`` read in ``zone`` (None: the host's), or None if invalid.

    As Java's SMART resolver: each field must be in its range, a day past the month's last day is
    clamped to it, and ``24:00`` is the start of the next day. Fold 0 takes the earlier offset in
    an overlap and moves a time in a gap forward, as Java's ``atZone``. A time that ``datetime``
    cannot hold (past 9999, in the zone or in UTC) is no end time.
    """
    match = PATTERN.fullmatch(text)
    if match is None:
        return None
    year, month, day, hour, minute = map(int, match.groups())
    valid_time = minute <= LAST_MINUTE and (hour <= LAST_HOUR or (hour, minute) == (END_OF_DAY, 0))
    if not (year and 1 <= month <= LAST_MONTH and 1 <= day <= LAST_DAY and valid_time):
        return None
    day = min(day, calendar.monthrange(year, month)[1])
    try:
        # Adding to a datetime keeps its wall time, so 24:00 becomes the next day's 00:00.
        moment = datetime(year, month, day, tzinfo=zone) + timedelta(hours=hour, minutes=minute)
        epoch = int(moment.timestamp())
        datetime.fromtimestamp(epoch, zone)  # it can be shown, also when UTC is past 9999
    except OverflowError, ValueError, OSError:
        return None
    return epoch


def format_end_time(epoch: int, zone: tzinfo | None) -> str:
    """``epoch`` as ``yyyy-MM-dd HH:mm`` in ``zone`` (None: the host's).

    The year has four digits: ``strftime("%Y")`` does not pad years below 1000 everywhere.
    """
    moment = datetime.fromtimestamp(epoch, zone)
    return (
        f"{moment.year:04d}-{moment.month:02d}-{moment.day:02d} "
        f"{moment.hour:02d}:{moment.minute:02d}"
    )
