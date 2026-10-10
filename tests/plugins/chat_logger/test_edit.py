"""The edits of stored messages, posted to the listen channels that detect the channel.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/Event.kt:115-119
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/ChatLogger.kt:132-172
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/DbManager.kt:96-112
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/resources/lang/en-US/message/on-msg-update.yaml:1-31
"""

from typing import TYPE_CHECKING

import discord
import pytest

import payloads
from discord_fakes import BOT_USER
from plugin_fakes import golden

if TYPE_CHECKING:
    from conftest import Scene

GOLDEN = golden("chat_logger")
REASON = "Edits of stored messages are logged"


def values(post: dict[str, object]) -> list[object]:
    """The field values of a posted embed, in the template's order."""
    fields = post["fields"]
    assert isinstance(fields, list)
    return [field["value"] for field in fields]  # pyright: ignore[reportUnknownVariableType]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_edit(scene: Scene, locale: str) -> None:
    """Requirement: Edits of stored messages are logged."""
    scene.guild.preferred_locale = discord.Locale(locale)  # v3 used the guild's locale
    await scene.listen(5, [30])
    await scene.send(100, 30, "hello")

    await scene.edit(100, 30, "hi")

    assert scene.posts(5) == [GOLDEN["update"][locale]]
    assert await scene.rows() == [(100, 10, 30, 7, "hi", 1)]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_second_edit(scene: Scene) -> None:
    """Requirement: Edits of stored messages are logged."""
    await scene.listen(5, [30])
    await scene.send(100, 30, "hello")
    await scene.edit(100, 30, "hi")

    await scene.edit(100, 30, "hey")

    second = scene.posts(5)[1]
    assert values(second)[3:] == ["2", "hi", "hey"]
    assert await scene.rows() == [(100, 10, 30, 7, "hey", 2)]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_same_text(scene: Scene) -> None:
    """Requirement: Edits of stored messages are logged."""
    await scene.listen(5, [30])
    await scene.send(100, 30, "see https://example.com")
    preview: payloads.Payload = {"type": "link", "title": "Example", "url": "https://example.com"}
    author = payloads.user(7, "user7")
    update = payloads.message(100, 30, 10, author, "see https://example.com", embeds=[preview])

    await scene.parse("MESSAGE_UPDATE", update)  # Discord's link preview
    await scene.edit(100, 30, "see https://example.com")  # a pin, or suppressed embeds

    # v3 counted and posted every update, and stored a preview's text instead of the content.
    assert scene.posts(5) == []
    assert await scene.rows() == [(100, 10, 30, 7, "see https://example.com", 0)]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_not_stored(scene: Scene) -> None:
    """Requirement: Edits of stored messages are logged."""
    await scene.listen(5, [30])

    await scene.edit(100, 30, "hi")  # sent before it could be stored

    assert scene.posts(5) == []
    assert await scene.rows() == []  # v3 did not store it on an edit either


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_not_detected(scene: Scene) -> None:
    """Requirement: Edits of stored messages are logged."""
    await scene.listen(5, [32])
    await scene.send(100, 30, "hello")

    await scene.edit(100, 30, "hi")

    assert scene.posts(5) == []
    assert await scene.rows() == [(100, 10, 30, 7, "hi", 1)]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_thread(scene: Scene) -> None:
    """Requirement: Edits of stored messages are logged."""
    await scene.listen(5, [30])  # thread 41's channel
    await scene.send(100, 41, "hello")

    await scene.edit(100, 41, "hi")

    # v3 threw for threads (asStandardGuildChannel), so their edits were never posted.
    [post] = scene.posts(5)
    assert values(post)[:3] == ["<@7>", "<#20>", "<#41>"]
    assert post["url"] == "https://discord.com/channels/10/41/100"


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_channel_without_a_category(scene: Scene) -> None:
    """Requirement: Edits of stored messages are logged."""
    await scene.listen(5, [33])
    await scene.send(100, 33, "hello")

    await scene.edit(100, 33, "hi")

    # v3 left the category unset there: an earlier event's category or the placeholder showed.
    [post] = scene.posts(5)
    assert values(post)[:3] == ["<@7>", "-", "<#33>"]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_webhook(scene: Scene) -> None:
    """Requirement: Edits of stored messages are logged."""
    await scene.listen(5, [30])
    webhook = payloads.user(500, "hook", bot=True)
    for event, text in (("MESSAGE_CREATE", "hello"), ("MESSAGE_UPDATE", "hi")):
        await scene.parse(event, payloads.message(100, 30, 10, webhook, text, webhook_id=500))

    # v3 rendered a webhook's edit with the global substitutor, which left the keys as written.
    [post] = scene.posts(5)
    assert values(post)[0] == "<@500>"
    assert "thumbnail" not in post


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=REASON)
async def test_the_bots_own_edit(scene: Scene) -> None:
    """Requirement: Edits of stored messages are logged."""
    await scene.listen(5, [30])

    await scene.edit(100, 30, "hi", author=BOT_USER.id)

    assert scene.posts(5) == []


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Logged texts are shown as written and fit an embed field",
)
async def test_typed_placeholders(scene: Scene) -> None:
    """Requirement: Logged texts are shown as written and fit an embed field."""
    await scene.listen(5, [30])
    await scene.send(100, 30, "%bot_id% %cl_msg_after%")

    await scene.edit(100, 30, "%user_mention%")

    # v3 expanded them, and a text naming cl_msg_after or cl_msg_before made the log throw.
    [post] = scene.posts(5)
    assert values(post)[4:] == ["%bot_id% %cl_msg_after%", "%user_mention%"]
