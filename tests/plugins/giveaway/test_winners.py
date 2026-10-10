"""Winners: each prize draws distinct participants, unique across prizes when the policy says so.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/data/GiveawayData.kt:67-102
"""

import random
from collections import Counter
from typing import TYPE_CHECKING, cast

import pytest

from xincord.plugins.giveaway.model import Policy, Prize, Winners, draw_winners

if TYPE_CHECKING:
    from xincord.core.bot import Bot
    from xincord.plugins.giveaway.cog import Giveaway

REASON = "Winners are drawn per prize"
PARTICIPANTS = (111, 222, 333)
SEEDS = range(200)


def seeded(seed: int) -> random.Random:
    """A generator whose draws repeat, as the tests need; the plugin draws with SystemRandom."""
    return random.Random(seed)  # noqa: S311 - reproducible draws, not secrets


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
def test_duplicates_allowed() -> None:
    """Requirement: Winners are drawn per prize."""
    prizes = (Prize("Nitro", 2), Prize("Sticker", 2))
    overlapping = 0
    for seed in SEEDS:
        nitro, sticker = draw_winners(prizes, Policy.ALLOW_DUPLICATE, PARTICIPANTS, seeded(seed))
        assert (nitro.prize_name, sticker.prize_name) == ("Nitro", "Sticker")
        for winners in (nitro, sticker):
            assert len(winners.winner_ids) == 2
            assert len(set(winners.winner_ids)) == 2  # never twice within one prize
            assert set(winners.winner_ids) <= set(PARTICIPANTS)
        overlapping += bool(set(nitro.winner_ids) & set(sticker.winner_ids))

    assert overlapping == len(SEEDS)  # two of three twice always share someone


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
def test_unique_across_prizes() -> None:
    """Requirement: Winners are drawn per prize."""
    prizes = (Prize("Nitro", 2), Prize("Sticker", 2), Prize("Badge", 1))
    for seed in SEEDS:
        nitro, sticker, badge = draw_winners(
            prizes, Policy.UNIQUE_ACROSS_PRIZES, PARTICIPANTS, seeded(seed)
        )
        assert len(nitro.winner_ids) == 2
        assert len(sticker.winner_ids) == 1  # what the first prize left
        assert badge == Winners("Badge", ())  # nobody left: v3's not enough participants
        drawn = nitro.winner_ids + sticker.winner_ids
        assert sorted(drawn) == sorted(PARTICIPANTS)


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
@pytest.mark.parametrize("policy", list(Policy))
def test_no_participants(policy: Policy) -> None:
    """Requirement: Winners are drawn per prize."""
    prizes = (Prize("Nitro", 1), Prize("Sticker", 3))

    results = draw_winners(prizes, policy, (), seeded(1))

    assert results == (Winners("Nitro", ()), Winners("Sticker", ()))


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
@pytest.mark.parametrize("policy", list(Policy))
def test_no_prizes(policy: Policy) -> None:
    """Requirement: Winners are drawn per prize."""
    assert draw_winners((), policy, PARTICIPANTS, seeded(1)) == ()


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
def test_short_pool_and_counts_below_one() -> None:
    """Requirement: Winners are drawn per prize."""
    prizes = (Prize("Nitro", 5), Prize("Sticker", 0), Prize("Badge", -3))

    nitro, sticker, badge = draw_winners(prizes, Policy.ALLOW_DUPLICATE, PARTICIPANTS, seeded(7))

    assert sorted(nitro.winner_ids) == sorted(PARTICIPANTS)  # all three of the five places
    assert len(sticker.winner_ids) == len(badge.winner_ids) == 1  # v3's coerceAtLeast(1)


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
def test_reproducible() -> None:
    """Requirement: Winners are drawn per prize."""
    prizes = (Prize("Nitro", 2), Prize("Sticker", 1))

    first = draw_winners(prizes, Policy.UNIQUE_ACROSS_PRIZES, PARTICIPANTS, seeded(42))
    again = draw_winners(prizes, Policy.UNIQUE_ACROSS_PRIZES, PARTICIPANTS, seeded(42))

    assert first == again


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
def test_uniform_draw() -> None:
    """Requirement: Winners are drawn per prize."""
    rng = seeded(2026)
    participants = (1, 2, 3, 4)
    draws = 8000

    wins = Counter(
        draw_winners((Prize("Nitro"),), Policy.ALLOW_DUPLICATE, participants, rng)[0].winner_ids[0]
        for _ in range(draws)
    )

    # Each participant wins a quarter of the draws, give or take five standard deviations.
    assert sorted(wins) == list(participants)
    assert all(abs(count - draws / 4) < 5 * (draws * 0.25 * 0.75) ** 0.5 for count in wins.values())


@pytest.mark.xfail(strict=True, reason=REASON)
async def test_system_random(bot: Bot) -> None:
    """Requirement: Winners are drawn per prize."""
    cog = cast("Giveaway", bot.get_cog("Giveaway"))

    assert isinstance(getattr(cog, "random", None), random.SystemRandom)
