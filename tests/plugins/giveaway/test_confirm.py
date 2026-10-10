"""Confirming a draft: v3's checks of the draft and of Administrator, then the post.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:247-295
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepData.kt:47-59
"""

from typing import TYPE_CHECKING

import pytest

from plugin_fakes import golden
from xincord.plugins.giveaway.model import Draft, Prize

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import FakeInteraction

GOLDEN = golden("giveaway")
CHECKS = "Confirming checks the draft and the administrator"
NOW = 1772244000  # the tests' clock
COMPLETE = Draft(title="Nitro", end_at=NOW + 3600, prizes=(Prize("Nitro", 1),))


def replied(interaction: FakeInteraction) -> object:
    """The interaction's only response, an ephemeral reply's text."""
    [(method, fields)] = interaction.sent
    assert method == "response.send_message"
    assert fields["ephemeral"] is True
    return fields["content"]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=CHECKS)
@pytest.mark.parametrize(
    ("draft", "problem"),
    [
        (Draft(), "no-title"),
        (Draft(title="  ", end_at=NOW + 60, prizes=(Prize("A"),)), "no-title"),
        (Draft(title="Nitro"), "no-end-time"),
        (Draft(title="Nitro", end_at=NOW, prizes=(Prize("A"),)), "no-end-time"),
        (Draft(title="Nitro", end_at=NOW - 1, prizes=(Prize("A"),)), "no-end-time"),
        (Draft(title="Nitro", end_at=NOW + 1), "no-prizes"),
    ],
)
@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_incomplete_draft(scene: Scene, draft: Draft, problem: str, locale: str) -> None:
    """Requirement: Confirming checks the draft and the administrator."""
    scene.keep(draft)

    # v3 checked the draft before the permission.
    pressed = await scene.press("confirm-create", scene.who(locale=locale, admin=False))

    assert replied(pressed) == GOLDEN["replies"][locale][problem]
    assert scene.draft() == draft


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=CHECKS)
@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_not_an_administrator(scene: Scene, locale: str) -> None:
    """Requirement: Confirming checks the draft and the administrator."""
    scene.keep(COMPLETE)

    pressed = await scene.press("confirm-create", scene.who(locale=locale, admin=False))

    assert replied(pressed) == GOLDEN["replies"][locale]["not-admin"]
    assert scene.draft() == COMPLETE
