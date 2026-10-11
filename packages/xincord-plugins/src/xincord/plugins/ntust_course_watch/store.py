"""The registrations, in the store as v3's document.

v3 kept them in MongoDB (database ``NtustCourse``, collection ``generated_cache``, ``_id``
``user_record_map``), the value ``{"<code>": {"<channel ID>": ["<user ID>", ...]}}``: Moshi wrote
the channels' ``Long`` keys as JSON names and the users as strings. The store keeps that value under
the same key, so that the planned v3 data import copies it unchanged. v3 never read it back after a
restart (``getTyped`` found no adapter for its ``HashMap``) and overwrote it at the next change.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/NtustCourse.kt:15-30
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/NtustCourse.kt:58-76
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xincord.core.storage import Store

NAMESPACE = "NtustCourseWatch"
KEY = "user_record_map"  # v3's document _id

# The registered members of each course code in each channel, in registration order.
type Registered = Mapping[str, Mapping[int, tuple[int, ...]]]


class DataError(Exception):
    """The registrations document is not v3's shape; it is left as it is."""


def parse_registrations(document: object) -> Registered:
    """The registrations of v3's document."""
    raise NotImplementedError


@dataclass(frozen=True)
class Registrations:
    """The registrations document in the store."""

    store: Store

    async def load(self) -> Registered:
        """The registrations; none when there is no document."""
        raise NotImplementedError

    async def add(self, code: str, channel: int, user: int) -> bool:
        """Register ``user`` for ``code`` in ``channel``; whether it was not registered yet."""
        raise NotImplementedError

    async def remove(self, code: str, channel: int, user: int) -> bool:
        """Unregister ``user`` from ``code`` in ``channel``; whether it was registered."""
        raise NotImplementedError

    async def forget(self, channel: int) -> bool:
        """Drop every registration in ``channel``; whether it had any."""
        raise NotImplementedError
