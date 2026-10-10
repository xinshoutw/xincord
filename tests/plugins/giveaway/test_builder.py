"""The builder's drafts: only the builder message that shows a user's draft drives it.

v3 looked the draft up by the user and the guild only, so an older builder message drove the
newest draft.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:16-79
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:313-319
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:125-149
"""

from typing import TYPE_CHECKING

import pytest

from plugin_fakes import golden
from xincord.plugins.giveaway.model import Draft

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import FakeInteraction

GOLDEN = golden("giveaway")


def expired(locale: str = "en-US") -> list[tuple[str, dict[str, object]]]:
    """v3's session-expired reply, ephemeral."""
    reply = GOLDEN["replies"][locale]["expired"]
    return [("response.send_message", {"content": reply, "ephemeral": True})]


def sent(interaction: FakeInteraction) -> list[tuple[str, dict[str, object]]]:
    """What the plugin sent for the interaction."""
    return list(interaction.sent)


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_no_draft(scene: Scene, locale: str) -> None:
    """Requirement: Only the latest builder of a draft works."""
    pressed = await scene.press("set-title", scene.who(locale=locale))
    submitted = await scene.submit("set-title", {"title": "Nitro"}, scene.who(locale=locale))

    assert sent(pressed) == expired(locale)
    assert sent(submitted) == expired(locale)
    assert scene.cog.drafts == {}


async def test_older_builder(scene: Scene) -> None:
    """Requirement: Only the latest builder of a draft works."""
    scene.keep(Draft(title="New"), scene.who(message_id=44))

    pressed = await scene.press("toggle-duplicate-policy", scene.who(message_id=43))
    submitted = await scene.submit("set-title", {"title": "Old"}, scene.who(message_id=43))

    assert sent(pressed) == expired()
    assert sent(submitted) == expired()
    assert scene.draft() == Draft(title="New")


async def test_someone_elses_draft(scene: Scene) -> None:
    """Requirement: Only the latest builder of a draft works."""
    scene.keep(Draft(title="Mine"))

    pressed = await scene.press("cancel", scene.who(user=8))

    assert sent(pressed) == expired()
    assert scene.draft() == Draft(title="Mine")


async def test_unknown_sub_action(scene: Scene) -> None:
    """Requirement: Only the latest builder of a draft works."""
    scene.keep(Draft(title="Mine"))

    pressed = await scene.press("other")
    submitted = await scene.submit("other", {"title": "x"})

    assert sent(pressed) == []
    assert sent(submitted) == []  # v3 re-rendered the preview for a modal
    assert scene.draft() == Draft(title="Mine")
