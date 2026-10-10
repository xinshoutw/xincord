"""Giveaways as v3 kept them: drafts, prizes, winners and the stored instances.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/data/GiveawayData.kt:7-102
"""

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    import random
    from collections.abc import Callable, Collection, Iterable, Sequence

    from xincord.core.storage import JSON

DEFAULT_LOCALE_TAG = "zh-TW"  # v3's localeTag default


class DataError(Exception):
    """A stored giveaway is not v3's shape; it is left as it is, and the message says where."""


class Policy(StrEnum):
    """Whether one participant may win several prizes; v3's ``WinnerDuplicatePolicy``."""

    ALLOW_DUPLICATE = "ALLOW_DUPLICATE"
    UNIQUE_ACROSS_PRIZES = "UNIQUE_ACROSS_PRIZES"


@dataclass(frozen=True)
class Prize:
    """A prize and how many winners it has; v3's ``GiveawayPrize``."""

    name: str
    winner_count: int = 1


@dataclass(frozen=True)
class Draft:
    """What the builder sets up, kept with the posted giveaway; v3's ``GiveawayConfig``."""

    title: str = ""
    description: str = ""
    sponsor: str = ""
    thumbnail_url: str = ""
    end_at: int = 0  # the end time's epoch second; 0 while unset
    policy: Policy = Policy.ALLOW_DUPLICATE
    prizes: tuple[Prize, ...] = ()


@dataclass(frozen=True)
class Winners:
    """A prize's winners, in the order they were drawn; v3's ``PrizeWinners``."""

    prize_name: str
    winner_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class Instance:
    """A posted giveaway; v3's ``GiveawayInstance``."""

    id: str
    guild_id: int
    channel_id: int
    message_id: int
    creator_id: int
    config: Draft
    locale_tag: str = DEFAULT_LOCALE_TAG  # the creator's Discord locale
    created_at: int = 0
    ended_at: int | None = None
    ended: bool = False
    participant_ids: tuple[int, ...] = ()
    winner_results: tuple[Winners, ...] = ()


ID_LENGTH = 16  # v3's IDs: the first 16 hexadecimal digits of a random UUID


def new_id(taken: Collection[str], random_hex: Callable[[], str]) -> str:
    """A new giveaway ID that ``taken`` lacks, from ``random_hex`` (a UUID's hex digits).

    As v3: the first 16 digits, drawn again while the guild has a giveaway with them.
    """
    candidates = iter(lambda: random_hex()[:ID_LENGTH], None)
    return next(candidate for candidate in candidates if candidate not in taken)


def draw_winners(
    prizes: Sequence[Prize], policy: Policy, participants: Iterable[int], rng: random.Random
) -> tuple[Winners, ...]:
    """Draw each prize's winners from ``participants``, as v3's ``drawPrizeWinners``.

    In prize order, each prize draws the smaller of its winner count (at least 1) and its pool's
    size, distinct and uniformly at random: from every participant when duplicates are allowed,
    else from those that no earlier prize drew. ``rng.sample`` draws the same distribution as v3's
    ``shuffled(random).take(k)``; the winners keep the order they were drawn in.
    """
    everyone = tuple(participants)
    left = everyone  # under unique winners, the participants that no earlier prize drew
    results: list[Winners] = []
    for prize in prizes:
        pool = everyone if policy is Policy.ALLOW_DUPLICATE else left
        picked = tuple(rng.sample(pool, min(max(prize.winner_count, 1), len(pool))))
        results.append(Winners(prize.name, picked))
        left = tuple(participant for participant in left if participant not in picked)
    return tuple(results)


def is_closed(instance: Instance, now: int) -> bool:
    """Whether joining is over: the giveaway is drawn or its end time has come, as in v3."""
    return instance.ended or now >= instance.config.end_at


def join(instance: Instance, user_id: int, now: int) -> tuple[str, Instance]:
    """v3's toggle: ``closed``, else the user ``joined`` or ``left`` the participants."""
    if is_closed(instance, now):
        return "closed", instance
    participants = instance.participant_ids
    if user_id in participants:
        left = tuple(participant for participant in participants if participant != user_id)
        return "left", replace(instance, participant_ids=left)
    return "joined", replace(instance, participant_ids=(*participants, user_id))


@dataclass(frozen=True)
class Drawer:
    """Who presses Draw Winners or Reroll, and whether they have Administrator."""

    user_id: int
    admin: bool


def draw(
    instance: Instance, drawer: Drawer, *, reroll: bool, now: int, rng: random.Random
) -> tuple[str, Instance]:
    """v3's draw and reroll by ``drawer``: the refusal, else ``drawn`` and the drawn giveaway.

    Drawing is for the creator or an administrator once the end time has come and before a draw;
    rerolling is for administrators once drawn. Both draw every prize from the participants.
    """
    admin = drawer.admin
    allowed = admin if reroll else admin or drawer.user_id == instance.creator_id
    if not allowed:
        return "not-allowed", instance
    if reroll and not instance.ended:
        return "not-drawn", instance
    if not reroll and instance.ended:
        return "already-drawn", instance
    if not reroll and now < instance.config.end_at:
        return "too-early", instance
    return "drawn", drawn(instance, now, rng)


def drawn(instance: Instance, now: int, rng: random.Random) -> Instance:
    """The giveaway drawn at ``now``: every prize's winners, ended at ``now``."""
    config = instance.config
    winners = draw_winners(config.prizes, config.policy, instance.participant_ids, rng)
    return replace(instance, winner_results=winners, ended=True, ended_at=now)


def parse_instance(entry: JSON, where: str) -> Instance:
    """Read v3's JSON of a giveaway, as Moshi did; ``where`` names it in errors.

    Missing optional fields take v3's defaults, except ``createdAtEpochSecond``, which Kotlin set to
    the time of reading and v3 never read: it reads as 0. ``endedAtEpochSecond`` may be null;
    an explicit null anywhere else fails, as in Moshi. Booleans are not integers. Duplicate
    participants read once, in order, as v3's set kept them. Unknown fields are ignored.

    Raises:
        DataError: The entry is not v3's shape.
    """
    fields = _object(entry, where, "the giveaway")
    ended_at = fields.get("endedAtEpochSecond")
    return Instance(
        id=_text(fields, "id", where),
        guild_id=_integer(fields, "guildId", where),
        channel_id=_integer(fields, "channelId", where),
        message_id=_integer(fields, "messageId", where),
        creator_id=_integer(fields, "creatorId", where),
        config=_draft(_required(fields, "config", where), where),
        locale_tag=_text(fields, "localeTag", where, DEFAULT_LOCALE_TAG),
        created_at=_integer(fields, "createdAtEpochSecond", where, 0),
        ended_at=None if ended_at is None else _integer(fields, "endedAtEpochSecond", where),
        ended=_flag(fields, "ended", where),
        participant_ids=tuple(dict.fromkeys(_integers(fields, "participantIds", where))),
        winner_results=tuple(
            Winners(
                _text(result, "prizeName", where),
                tuple(_integers(result, "winnerIds", where)),
            )
            for result in _objects(fields, "winnerResults", where)
        ),
    )


def instance_json(instance: Instance) -> dict[str, JSON]:
    """v3's JSON of ``instance``, in Moshi's field order; an unset end time is left out."""
    config = instance.config
    draft: dict[str, JSON] = {
        "title": config.title,
        "description": config.description,
        "sponsor": config.sponsor,
        "thumbnailUrl": config.thumbnail_url,
        "endAtEpochSecond": config.end_at,
        "winnerDuplicatePolicy": config.policy.value,
        "prizes": [
            {"name": prize.name, "winnerCount": prize.winner_count} for prize in config.prizes
        ],
    }
    ended_at: dict[str, JSON] = (
        {} if instance.ended_at is None else {"endedAtEpochSecond": instance.ended_at}
    )
    return {
        "id": instance.id,
        "guildId": instance.guild_id,
        "channelId": instance.channel_id,
        "messageId": instance.message_id,
        "creatorId": instance.creator_id,
        "localeTag": instance.locale_tag,
        "createdAtEpochSecond": instance.created_at,
        **ended_at,
        "ended": instance.ended,
        "config": draft,
        "participantIds": list(instance.participant_ids),
        "winnerResults": [
            {"prizeName": result.prize_name, "winnerIds": list(result.winner_ids)}
            for result in instance.winner_results
        ],
    }


def _draft(value: JSON, where: str) -> Draft:
    """v3's ``GiveawayConfig``, every field optional."""
    fields = _object(value, where, "config")
    policy = _text(fields, "winnerDuplicatePolicy", where, Policy.ALLOW_DUPLICATE.value)
    if policy not in Policy:
        msg = f"{where}: unknown winnerDuplicatePolicy {policy!r}"
        raise DataError(msg)
    return Draft(
        title=_text(fields, "title", where, ""),
        description=_text(fields, "description", where, ""),
        sponsor=_text(fields, "sponsor", where, ""),
        thumbnail_url=_text(fields, "thumbnailUrl", where, ""),
        end_at=_integer(fields, "endAtEpochSecond", where, 0),
        policy=Policy(policy),
        prizes=tuple(
            Prize(_text(prize, "name", where), _integer(prize, "winnerCount", where, 1))
            for prize in _objects(fields, "prizes", where)
        ),
    )


def _object(value: JSON, where: str, what: str) -> dict[str, JSON]:
    if not isinstance(value, dict):
        msg = f"{where}: {what} is not a JSON object: {value!r}"
        raise DataError(msg)
    return value


def _required(fields: dict[str, JSON], key: str, where: str) -> JSON:
    """A field without a default: Moshi failed without it, and for null."""
    value = fields.get(key)
    if value is None:
        msg = f"{where}: {key} is missing or null"
        raise DataError(msg)
    return value


def _field(fields: dict[str, JSON], key: str, where: str, default: JSON) -> JSON:
    """A field with v3's default when it is missing; None as the default makes it required."""
    return default if key not in fields and default is not None else _required(fields, key, where)


def _text(fields: dict[str, JSON], key: str, where: str, default: str | None = None) -> str:
    value = _field(fields, key, where, default)
    if not isinstance(value, str):
        msg = f"{where}: {key} is not a text: {value!r}"
        raise DataError(msg)
    return value


def _integer(fields: dict[str, JSON], key: str, where: str, default: int | None = None) -> int:
    value = _field(fields, key, where, default)
    if type(value) is not int:  # booleans and fractions are no snowflakes or seconds
        msg = f"{where}: {key} is not an integer: {value!r}"
        raise DataError(msg)
    return value


def _flag(fields: dict[str, JSON], key: str, where: str) -> bool:
    value = _field(fields, key, where, False)  # noqa: FBT003 - v3's default
    if type(value) is not bool:
        msg = f"{where}: {key} is not a boolean: {value!r}"
        raise DataError(msg)
    return value


def _list(fields: dict[str, JSON], key: str, where: str) -> list[JSON]:
    value = _field(fields, key, where, [])
    if not isinstance(value, list):
        msg = f"{where}: {key} is not a list: {value!r}"
        raise DataError(msg)
    return value


def _integers(fields: dict[str, JSON], key: str, where: str) -> list[int]:
    items = _list(fields, key, where)
    if not all(type(item) is int for item in items):
        msg = f"{where}: {key} holds something that is not an integer: {items!r}"
        raise DataError(msg)
    return cast("list[int]", items)


def _objects(fields: dict[str, JSON], key: str, where: str) -> list[dict[str, JSON]]:
    return [_object(item, where, key) for item in _list(fields, key, where)]
