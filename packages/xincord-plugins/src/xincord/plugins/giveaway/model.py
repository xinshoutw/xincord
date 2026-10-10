"""Giveaways as v3 kept them: drafts, prizes, winners and the stored instances.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/data/GiveawayData.kt:7-102
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import random
    from collections.abc import Iterable, Sequence

DEFAULT_LOCALE_TAG = "zh-TW"  # v3's localeTag default


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
