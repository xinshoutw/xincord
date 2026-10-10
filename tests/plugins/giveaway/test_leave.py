"""Leaving a guild: its drafts go, its giveaways stay (v3 deleted the guild's file).

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Event.kt:109-112
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:151-154
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:153-155
"""

from typing import TYPE_CHECKING

from discord_fakes import FakeGuild
from plugin_fakes import dispatch, golden
from xincord.plugins.giveaway.cog import Session
from xincord.plugins.giveaway.model import Draft, Instance

if TYPE_CHECKING:
    from conftest import Scene

GOLDEN = golden("giveaway")


async def test_left_guild(scene: Scene) -> None:
    """Requirement: Leaving a guild drops its drafts."""
    scene.keep(Draft(title="Nitro"))  # user 7 in guild 10
    scene.cog.drafts[7, 11] = Session(44, Draft(title="Elsewhere"))
    giveaway = Instance("3f2a9c1b7e4d4a60", 10, 5, 500, 7, Draft(title="Nitro"))
    await scene.add(giveaway)

    await dispatch(scene.bot, "guild_remove", FakeGuild(10).as_guild())

    pressed = await scene.press("set-title")
    reply = GOLDEN["replies"]["en-US"]["expired"]
    assert pressed.sent == [("response.send_message", {"content": reply, "ephemeral": True})]
    assert scene.cog.drafts == {(7, 11): Session(44, Draft(title="Elsewhere"))}
    assert await scene.stored(giveaway.id) == giveaway  # kept for rerolls after a return
