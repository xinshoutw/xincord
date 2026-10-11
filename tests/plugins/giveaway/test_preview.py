"""The builder's preview: v3's green embed of the draft, with long fields clipped."""

from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

import pytest

from discord_fakes import embed_dict
from plugin_fakes import golden
from xincord.plugins.giveaway.model import Draft, Policy, Prize
from xincord.plugins.giveaway.texts import Texts, preview

if TYPE_CHECKING:
    from xincord.core.bot import Bot
    from xincord.plugins.giveaway.cog import Giveaway

REASON = "The preview shows the draft"
GOLDEN = golden("giveaway")
TAIPEI = ZoneInfo("Asia/Taipei")
FULL = Draft(
    title="Nitro",
    description="desc",
    sponsor="Shop",
    thumbnail_url="HTTPS://EXAMPLE.COM/a.png",
    end_at=1772330400,
    policy=Policy.UNIQUE_ACROSS_PRIZES,
    prizes=(Prize("Nitro", 2), Prize("Sticker", 0)),
)


def texts(bot: Bot, locale: str) -> Texts:
    """The loaded plugin's texts in ``locale``."""
    return Texts(cast("Giveaway", bot.get_cog("Giveaway")).lang, locale)


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_empty_draft(bot: Bot, locale: str) -> None:
    """Requirement: The preview shows the draft."""
    embed = preview(Draft(), texts(bot, locale), TAIPEI)

    assert embed_dict(embed) == GOLDEN["preview"][locale]["empty"]


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_full_draft(bot: Bot, locale: str) -> None:
    """Requirement: The preview shows the draft."""
    embed = preview(FULL, texts(bot, locale), TAIPEI)

    assert embed_dict(embed) == GOLDEN["preview"][locale]["full"]


async def test_long_texts(bot: Bot) -> None:
    """Requirement: The preview shows the draft."""
    prizes = tuple(Prize(f"Prize number {index} " + "x" * 60, 1) for index in range(40))
    draft = Draft(description="d" * 4000, prizes=prizes)

    embed = preview(draft, texts(bot, "en-US"), TAIPEI)

    description, _, prize_list, *_ = embed.fields
    assert description.value == "d" * 1021 + "..."
    assert prize_list.value is not None
    assert len(prize_list.value) == 1024
    assert prize_list.value.startswith("1. Prize number 0 ")
    assert prize_list.value.endswith("...")
    assert len(embed) <= 6000


async def test_typed_placeholders(bot: Bot) -> None:
    """Requirement: The preview shows the draft."""
    draft = Draft(title="%ga@title%", description="%bot_name%", sponsor="%ga@index%")

    embed = embed_dict(preview(draft, texts(bot, "en-US"), TAIPEI))

    # The title is v3's "<gift> Nitro" with the typed title instead, as written.
    assert embed["title"] == GOLDEN["preview"]["en-US"]["full"]["title"].replace(
        "Nitro", "%ga@title%"
    )
    values = [field["value"] for field in embed["fields"]]
    assert values[0] == "%bot_name%"
    assert values[5] == "%ga@index%"
