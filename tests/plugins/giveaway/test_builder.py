"""The builder's drafts: the latest builder of a draft drives it; prizes and the winner policy.

v3 looked the draft up by the user and the guild only, so an older builder message drove the
newest draft.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:16-79
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:209-225
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:297-363
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepData.kt:34-45
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:125-149
"""

from typing import TYPE_CHECKING, Any, cast

import discord
import pytest

from discord_fakes import embed_dict
from plugin_fakes import golden
from xincord.plugins.giveaway.model import Draft, Policy, Prize

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import FakeInteraction

GOLDEN = golden("giveaway")
CANCEL = "Cancelling ends the draft"


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


def preview_fields(interaction: FakeInteraction) -> list[dict[str, Any]]:
    """The fields of the preview that replaced the builder, the interaction's only response."""
    [(method, fields)] = interaction.sent
    assert method == "response.edit_message"
    assert isinstance(fields["view"], discord.ui.View)
    [embed] = cast("tuple[discord.Embed, ...]", fields["embeds"])
    found: list[dict[str, Any]] = embed_dict(embed)["fields"]
    return found


async def test_remove_prize(scene: Scene) -> None:
    """Requirement: The builder removes prizes and switches the winner policy."""
    scene.keep(Draft(prizes=(Prize("Nitro", 2), Prize("Sticker", 1))))

    pressed = await scene.press("remove-prize")

    assert scene.draft() == Draft(prizes=(Prize("Nitro", 2),))
    expected = GOLDEN["preview"]["en-US"]["full"]["fields"][2]["value"].partition("\n")[0]
    assert preview_fields(pressed)[2]["value"] == expected


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_nothing_to_remove(scene: Scene, locale: str) -> None:
    """Requirement: The builder removes prizes and switches the winner policy."""
    scene.keep(Draft(title="Nitro"))

    pressed = await scene.press("remove-prize", scene.who(locale=locale))

    reply = GOLDEN["replies"][locale]["no-prize"]
    assert sent(pressed) == [("response.send_message", {"content": reply, "ephemeral": True})]
    assert scene.draft() == Draft(title="Nitro")


async def test_switch_policy(scene: Scene) -> None:
    """Requirement: The builder removes prizes and switches the winner policy."""
    scene.keep(Draft())
    unique = GOLDEN["preview"]["en-US"]["full"]["fields"][3]["value"]
    allowed = GOLDEN["preview"]["en-US"]["empty"]["fields"][3]["value"]

    first = await scene.press("toggle-duplicate-policy")
    assert scene.draft().policy is Policy.UNIQUE_ACROSS_PRIZES
    second = await scene.press("toggle-duplicate-policy")

    assert scene.draft().policy is Policy.ALLOW_DUPLICATE
    assert preview_fields(first)[3]["value"] == unique
    assert preview_fields(second)[3]["value"] == allowed


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=CANCEL)
@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_cancelled(scene: Scene, locale: str) -> None:
    """Requirement: Cancelling ends the draft."""
    scene.keep(Draft(title="Nitro"))
    who = scene.who(locale=locale)

    pressed = await scene.press("cancel", who)
    later = await scene.press("set-title", who)

    # v3's replace edit: the cancelled text alone, without the preview and the buttons.
    edited = {"content": GOLDEN["cancelled"][locale], "embeds": (), "view": None, "attachments": ()}
    assert sent(pressed) == [("response.edit_message", edited)]
    assert scene.cog.drafts == {}
    assert sent(later) == expired(locale)
