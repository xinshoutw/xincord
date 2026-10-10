"""Submitted modals: a valid one changes the draft and the builder, an invalid one gets v3's error.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:70-151
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepData.kt:22-32
"""

from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

import discord
import pytest

from discord_fakes import embed_dict
from plugin_fakes import golden
from xincord.plugins.giveaway.drafts import submit
from xincord.plugins.giveaway.model import Draft, Prize

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import FakeInteraction

GOLDEN = golden("giveaway")
TAIPEI = 'timeZone: "Asia/Taipei"\n'
NEXT_LINE = chr(0x85)


def shown(interaction: FakeInteraction) -> discord.Embed:
    """The preview of the builder message that the submission replaced, its only response."""
    [(method, fields)] = interaction.sent
    assert method == "response.edit_message"
    assert fields["content"] == ""
    assert isinstance(fields["view"], discord.ui.View)  # the builder's buttons stay
    [embed] = cast("tuple[discord.Embed, ...]", fields["embeds"])
    return embed


def reply(interaction: FakeInteraction) -> object:
    """The text of the interaction's only response, an ephemeral reply."""
    [(method, fields)] = interaction.sent
    assert method == "response.send_message"
    assert fields["ephemeral"] is True
    return fields["content"]


async def test_title(scene: Scene) -> None:
    """Requirement: Submitted modals change the draft."""
    scene.keep(Draft())

    submitted = await scene.submit("set-title", {"title": " Nitro "})

    assert scene.draft() == Draft(title="Nitro")
    assert embed_dict(shown(submitted))["title"] == GOLDEN["preview"]["en-US"]["full"]["title"]


async def test_kotlin_trim(scene: Scene) -> None:
    """Requirement: Submitted modals change the draft."""
    scene.keep(Draft())

    await scene.submit("set-title", {"title": f"{NEXT_LINE}Nitro "})

    assert scene.draft().title == f"{NEXT_LINE}Nitro"  # Kotlin's trim keeps U+0085


@pytest.mark.parametrize("config", [TAIPEI])
async def test_end_time(scene: Scene) -> None:
    """Requirement: Submitted modals change the draft."""
    scene.keep(Draft())

    submitted = await scene.submit("set-end-time", {"end-time": "2026-03-01 10:00"})

    assert scene.draft() == Draft(end_at=1772330400)
    end_time = embed_dict(shown(submitted))["fields"][1]["value"]
    assert end_time == "<t:1772330400:F>\n2026-03-01 10:00"


@pytest.mark.parametrize("config", [TAIPEI])
@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
@pytest.mark.parametrize(
    ("sub_action", "values", "error"),
    [
        ("set-title", {"title": "   "}, "title"),
        ("set-title", {}, "title"),
        ("set-end-time", {"end-time": " "}, "end-time"),
        ("set-end-time", {"end-time": "2026-1-5 9:00"}, "end-time-format"),
        ("set-end-time", {"end-time": "2026-02-28 10:00"}, "end-time-past"),  # the clock's now
        ("set-end-time", {"end-time": "2026-02-27 10:00"}, "end-time-past"),
        ("add-prize", {"prize-name": " ", "winner-count": "1"}, "prize-name"),
        ("add-prize", {"prize-name": "Nitro", "winner-count": "51"}, "winner-count"),
        ("add-prize", {"prize-name": "Nitro", "winner-count": ""}, "winner-count"),
        ("set-thumbnail", {"thumbnail": "ftp://x.com"}, "thumbnail"),
    ],
)
async def test_errors(
    scene: Scene, sub_action: str, values: dict[str, str], error: str, locale: str
) -> None:
    """Requirement: Submitted modals change the draft."""
    draft = Draft(title="Nitro", thumbnail_url="https://x/y.png", prizes=(Prize("A", 1),))
    scene.keep(draft)

    submitted = await scene.submit(sub_action, values, scene.who(locale=locale))

    assert reply(submitted) == GOLDEN["replies"][locale][error]
    assert scene.draft() == draft


async def test_prizes(scene: Scene) -> None:
    """Requirement: Submitted modals change the draft."""
    scene.keep(Draft())

    for index in range(60):  # no limit on the number of prizes, as in v3
        await scene.submit("add-prize", {"prize-name": f" P{index} ", "winner-count": "+2"})

    assert scene.draft().prizes == tuple(Prize(f"P{index}", 2) for index in range(60))


async def test_cleared(scene: Scene) -> None:
    """Requirement: Submitted modals change the draft."""
    scene.keep(Draft(description="desc", sponsor="Shop", thumbnail_url="https://x/y.png"))

    await scene.submit("set-description", {"description": ""})
    await scene.submit("set-sponsor", {"sponsor": "  "})
    submitted = await scene.submit("set-thumbnail", {})

    assert scene.draft() == Draft()
    embed = embed_dict(shown(submitted))
    assert "thumbnail" not in embed
    not_set = GOLDEN["preview"]["en-US"]["empty"]["fields"][0]["value"]
    assert [field["value"] for field in embed["fields"]][0::5] == [not_set, not_set]


async def test_values_as_typed(scene: Scene) -> None:
    """Requirement: Submitted modals change the draft."""
    scene.keep(Draft())

    await scene.submit("set-description", {"description": "%bot_name%\nline"})
    await scene.submit("set-sponsor", {"sponsor": "%user_id%"})
    await scene.submit("set-thumbnail", {"thumbnail": "HTTPS://EXAMPLE.COM/a.png"})

    assert scene.draft() == Draft(
        description="%bot_name%\nline",
        sponsor="%user_id%",
        thumbnail_url="HTTPS://EXAMPLE.COM/a.png",
    )


def test_unknown_modal() -> None:
    """Requirement: Submitted modals change the draft."""
    draft = Draft(title="Nitro")

    assert submit(draft, "other", {"title": "x"}, 0, ZoneInfo("UTC")) == draft
