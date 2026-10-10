"""The post: v3's embed and buttons of a giveaway, in the creator's language.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:471-633
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/resources/lang/en-US/message/giveaway-post.yaml:1-9
"""

from dataclasses import replace
from typing import TYPE_CHECKING, Any

import discord
import pytest

from discord_fakes import embed_dict
from plugin_fakes import golden
from xincord.plugins.giveaway.inputs import units
from xincord.plugins.giveaway.model import Draft, Instance, Policy, Prize, Winners

if TYPE_CHECKING:
    from conftest import Scene

GOLDEN = golden("giveaway")
REASON = "The post shows the giveaway"
END = 1772330400
RUNNING = Instance(
    id="3f2a9c1b7e4d4a60",
    guild_id=10,
    channel_id=5,
    message_id=500,
    creator_id=7,
    config=Draft(
        title="Nitro",
        thumbnail_url="https://x/y.png",
        end_at=END,
        prizes=(Prize("Nitro", 2), Prize("Sticker", 1)),
    ),
    participant_ids=(111, 222),
)
DRAWN = replace(
    RUNNING,
    config=replace(
        RUNNING.config, description="desc", sponsor="Shop", policy=Policy.UNIQUE_ACROSS_PRIZES
    ),
    participant_ids=(111, 222, 333),
    ended=True,
    ended_at=END + 60,
    winner_results=(Winners("Nitro", (222, 111)), Winners("Sticker", ())),
)


def rendered(scene: Scene, instance: Instance) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    """The post's embed as a dict, and each button's style, label, ID and disabled state."""
    message = scene.cog.render_post(instance)
    [embed] = message.embeds
    view = message.view
    assert isinstance(view, discord.ui.View)
    buttons = [
        (item.style.value, item.label, item.custom_id, item.disabled)
        for item in view.children
        if isinstance(item, discord.ui.Button)
    ]
    assert message.content == ""
    return embed_dict(embed), buttons


def expected_buttons(locale: str, disabled: tuple[bool, bool, bool]) -> list[tuple[Any, ...]]:
    """v3's three buttons in ``locale`` with the giveaway's new IDs."""
    shape = GOLDEN["post-buttons"]
    return [
        (style, label, f"giveaway:1:a={action};c=3f2a9c1b7e4d4a60", off)
        for style, label, action, off in zip(
            shape["styles"],
            GOLDEN["post"][locale]["buttons"],
            shape["actions"],
            disabled,
            strict=True,
        )
    ]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_running(scene: Scene, locale: str) -> None:
    """Requirement: The post shows the giveaway."""
    embed, buttons = rendered(scene, replace(RUNNING, locale_tag=locale))

    assert embed == GOLDEN["post"][locale]["running"]
    assert buttons == expected_buttons(locale, (False, False, True))


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_drawn(scene: Scene, locale: str) -> None:
    """Requirement: The post shows the giveaway."""
    embed, buttons = rendered(scene, replace(DRAWN, locale_tag=locale))

    assert embed == GOLDEN["post"][locale]["drawn"]
    assert buttons == expected_buttons(locale, (True, True, False))


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_ready_to_draw(scene: Scene, locale: str) -> None:
    """Requirement: The post shows the giveaway."""
    scene.cog.clock = lambda: END  # the end time has come; nothing drew it yet

    embed, buttons = rendered(scene, replace(RUNNING, locale_tag=locale))

    status = f"{GOLDEN['post'][locale]['ready']}\n<t:{END}:R>"
    assert embed["fields"][0]["value"] == status
    assert buttons == expected_buttons(locale, (True, False, True))  # closed for joins


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_language_of_the_creator(scene: Scene) -> None:
    """Requirement: The post shows the giveaway."""
    for tag, shown in (("zh-CN", "zh-TW"), ("en-GB", "en-US"), ("unknown", "en-US")):
        embed, _ = rendered(scene, replace(RUNNING, locale_tag=tag))
        assert embed == GOLDEN["post"][shown]["running"]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_typed_title(scene: Scene) -> None:
    """Requirement: The post shows the giveaway."""
    instance = replace(RUNNING, config=replace(RUNNING.config, title="%bot_name% %ga@id%"))

    embed, _ = rendered(scene, instance)

    title = GOLDEN["post"]["en-US"]["running"]["title"].replace("Nitro", "%bot_name% %ga@id%")
    assert embed["title"] == title


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_long_texts(scene: Scene) -> None:
    """Requirement: The post shows the giveaway."""
    prizes = tuple(Prize(f"Prize number {index} " + "x" * 60, 1) for index in range(40))
    winners = (Winners("Nitro", tuple(range(10**17, 10**17 + 50))),)
    config = replace(RUNNING.config, description="d" * 4000, sponsor="s" * 100, prizes=prizes)
    instance = replace(DRAWN, config=config, winner_results=winners)

    embed = scene.cog.render_post(instance).embeds[0]

    values = [field.value or "" for field in embed.fields]
    assert all(units(value) <= 1024 for value in values)
    assert values[3].endswith("...")
    assert values[4].endswith("...")
    parts = [embed.title, embed.description, embed.footer.text]
    parts += [part for field in embed.fields for part in (field.name, field.value)]
    assert sum(units(part or "") for part in parts) <= 6000
    assert (embed.description or "").endswith("...")
