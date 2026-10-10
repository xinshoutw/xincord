"""Only the builder message that shows a draft drives it.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepManager.kt:17-18
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepManager.kt:93-95
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepManager.kt:253-254
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepManager.kt:280-281
"""

from typing import TYPE_CHECKING

import pytest

from xincord.plugins.ticket.model import Draft

if TYPE_CHECKING:
    from conftest import Scene, Who
    from discord_fakes import FakeInteraction

EXPIRED = (
    "response.send_message",
    {"content": "This setup has expired; run the command again.", "ephemeral": True},
)
ACTS = ["press", "choose", "submit"]


async def act(scene: Scene, how: str, who: Who) -> FakeInteraction:
    """``who`` uses the builder: a button, a select or a modal."""
    match how:
        case "press":
            return await scene.press("modify-author", who)
        case "choose":
            return await scene.choose("modify-category", ["30"], who)
        case _:
            return await scene.submit("modify-reason", {"reason": "Why?"}, who)


@pytest.mark.parametrize("how", ACTS)
async def test_no_draft(scene: Scene, how: str) -> None:
    """Requirement: Only the latest builder of a draft works."""
    interaction = await act(scene, how, scene.who())

    # v3 acknowledged silently without a step, so a builder after a restart did nothing.
    assert interaction.sent == [EXPIRED]
    assert scene.cog.drafts == {}


@pytest.mark.parametrize("how", ACTS)
async def test_older_builder(scene: Scene, how: str) -> None:
    """Requirement: Only the latest builder of a draft works."""
    scene.keep(Draft("Old"), scene.who(message_id=44))  # the newest builder is message 44

    interaction = await act(scene, how, scene.who(message_id=43))

    # v3 found the step by the user only, so any of their builders drove the newest draft.
    assert interaction.sent == [EXPIRED]
    assert scene.session().draft == Draft("Old")
    assert scene.session().message_id == 44


async def test_another_users_draft(scene: Scene) -> None:
    """Requirement: Only the latest builder of a draft works."""
    scene.keep(Draft("Old"))  # administrator 7's draft in builder 43

    interaction = await scene.press("modify-author", scene.who(user=9))

    assert interaction.sent == [EXPIRED]
