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

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from .courses import course_code

if TYPE_CHECKING:
    from collections.abc import Callable

    from xincord.core.storage import JSON, Store

NAMESPACE = "NtustCourseWatch"
KEY = "user_record_map"  # v3's document _id
LOCK = f"{NAMESPACE}:{KEY}"  # every change of the document holds it
DECIMAL = re.compile(r"[0-9]+")  # a snowflake as v3 wrote it

# The registered members of each course code in each channel, in registration order.
type Registered = Mapping[str, Mapping[int, tuple[int, ...]]]
type Change = Callable[[Registered], Registered | None]  # None: nothing to change


class DataError(Exception):
    """The registrations document is not v3's shape; it is left as it is."""


def parse_registrations(document: object) -> Registered:
    """The registrations of v3's document; none for no document.

    A member listed twice (v3's ``/course-add`` allowed it) counts once, and channels and courses
    without members (v3's ``/course-remove`` left the latter) are left out. Codes are read as
    ``/course-add`` reads them, since v3 stored them as typed: the registrations of codes that read
    as one are merged, and codes that are no course code (an empty one would ask for the whole
    semester) are left out; the next change writes the document without them.

    Raises:
        DataError: The document is not an object of courses whose channels, keyed by their IDs,
            list their members' IDs as text.
    """
    if document is None:
        return {}
    if not isinstance(document, dict):
        msg = "the registrations are not v3's document: expected an object of courses"
        raise DataError(msg)
    registered: dict[str, Mapping[int, tuple[int, ...]]] = {}
    for stored, channels in cast("dict[str, object]", document).items():
        members = _channels(stored, channels)
        code = course_code(stored)
        if code is not None and members:
            registered[code] = _merged(registered.get(code, {}), members)
    return registered


def _merged(
    first: Mapping[int, tuple[int, ...]], second: Mapping[int, tuple[int, ...]]
) -> dict[int, tuple[int, ...]]:
    """The members of both, per channel, in order and once each."""
    merged = dict(first)
    for channel, members in second.items():
        merged[channel] = tuple(dict.fromkeys((*merged.get(channel, ()), *members)))
    return merged


def _channels(code: str, channels: object) -> dict[int, tuple[int, ...]]:
    if not isinstance(channels, dict):
        msg = f"course {code}: expected an object of channels"
        raise DataError(msg)
    parsed: dict[int, tuple[int, ...]] = {}
    for channel, users in cast("dict[str, object]", channels).items():
        if DECIMAL.fullmatch(channel) is None:
            msg = f"course {code}: the channel {channel!r} is not an ID"
            raise DataError(msg)
        if not isinstance(users, list):
            msg = f"course {code}, channel {channel}: expected a list of members"
            raise DataError(msg)
        members: dict[int, None] = {}  # in order, once each
        for user in cast("list[object]", users):
            if not isinstance(user, str) or DECIMAL.fullmatch(user) is None:
                msg = f"course {code}, channel {channel}: a member is not an ID as text"
                raise DataError(msg)
            members[int(user)] = None
        if members:
            parsed[int(channel)] = tuple(members)
    return parsed


def registrations_document(registered: Registered) -> dict[str, JSON]:
    """v3's document of the registrations: IDs as text, channels keyed by theirs."""
    return {
        code: {str(channel): [str(user) for user in users] for channel, users in channels.items()}
        for code, channels in registered.items()
    }


def _with(code: str, channel: int, user: int) -> Change:
    def change(registered: Registered) -> Registered | None:
        channels = registered.get(code, {})
        members = channels.get(channel, ())
        if user in members:
            return None
        return {**registered, code: {**channels, channel: (*members, user)}}

    return change


def _without(code: str, channel: int, user: int) -> Change:
    def change(registered: Registered) -> Registered | None:
        channels = registered.get(code, {})
        members = channels.get(channel, ())
        if user not in members:
            return None
        kept = tuple(member for member in members if member != user)
        rest = {key: value for key, value in channels.items() if key != channel}
        if kept:
            rest[channel] = kept
        return _courses(registered, code, rest)

    return change


def _forgotten(channel: int) -> Change:
    def change(registered: Registered) -> Registered | None:
        if not any(channel in channels for channels in registered.values()):
            return None
        return {
            code: rest
            for code, channels in registered.items()
            if (rest := {key: value for key, value in channels.items() if key != channel})
        }

    return change


def _courses(
    registered: Registered, code: str, channels: Mapping[int, tuple[int, ...]]
) -> Registered:
    """``registered`` with ``code``'s channels replaced, the course dropped without any."""
    rest = {key: value for key, value in registered.items() if key != code}
    if channels:
        rest[code] = channels
    return rest


@dataclass(frozen=True)
class Registrations:
    """The registrations document in the store.

    Every change reads the document under :data:`LOCK` and writes it only when it changed, since
    discord.py runs the commands of several members at once; the document goes with its last
    registration.
    """

    store: Store

    async def load(self) -> Registered:
        """The registrations; none when there is no document.

        Raises:
            DataError: The document is not v3's shape.
        """
        return parse_registrations(await self.store.get(NAMESPACE, KEY))

    async def add(self, code: str, channel: int, user: int) -> bool:
        """Register ``user`` for ``code`` in ``channel``; whether it was not registered yet.

        Raises:
            DataError: The document is not v3's shape; it is left as it is.
        """
        return await self._change(_with(code, channel, user))

    async def remove(self, code: str, channel: int, user: int) -> bool:
        """Unregister ``user`` from ``code`` in ``channel``; whether it was registered.

        Raises:
            DataError: The document is not v3's shape; it is left as it is.
        """
        return await self._change(_without(code, channel, user))

    async def forget(self, channel: int) -> bool:
        """Drop every registration in ``channel``; whether it had any.

        Raises:
            DataError: The document is not v3's shape; it is left as it is.
        """
        return await self._change(_forgotten(channel))

    async def _change(self, change: Change) -> bool:
        async with self.store.lock(LOCK):
            changed = change(await self.load())
            if changed is None:
                return False
            if changed:
                await self.store.put(NAMESPACE, KEY, registrations_document(changed))
            else:
                await self.store.delete(NAMESPACE, KEY)
            return True
