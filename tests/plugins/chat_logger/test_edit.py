"""The edits of stored messages, posted to the listen channels that detect the channel."""

from typing import TYPE_CHECKING

import discord
import pytest

import payloads
from discord_fakes import BOT_USER
from plugin_fakes import burst, golden

if TYPE_CHECKING:
    from conftest import Scene

GOLDEN = golden("chat_logger")


def values(post: dict[str, object]) -> list[object]:
    """The field values of a posted embed, in the template's order."""
    fields = post["fields"]
    assert isinstance(fields, list)
    return [field["value"] for field in fields]  # pyright: ignore[reportUnknownVariableType]


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_edit(scene: Scene, locale: str) -> None:
    """Requirement: Edits of stored messages are logged."""
    scene.guild.preferred_locale = discord.Locale(locale)  # the guild's locale
    await scene.listen(5, [30])
    await scene.send(100, 30, "hello")

    await scene.edit(100, 30, "hi")

    assert scene.posts(5) == [GOLDEN["update"][locale]]
    assert await scene.rows() == [(100, 10, 30, 7, "hi", 1)]


async def test_second_edit(scene: Scene) -> None:
    """Requirement: Edits of stored messages are logged."""
    await scene.listen(5, [30])
    await scene.send(100, 30, "hello")
    await scene.edit(100, 30, "hi")

    await scene.edit(100, 30, "hey")

    second = scene.posts(5)[1]
    assert values(second)[3:] == ["2", "hi", "hey"]
    assert await scene.rows() == [(100, 10, 30, 7, "hey", 2)]


async def test_same_text(scene: Scene) -> None:
    """Requirement: Edits of stored messages are logged."""
    await scene.listen(5, [30])
    await scene.send(100, 30, "see https://example.com")
    preview: payloads.Payload = {"type": "link", "title": "Example", "url": "https://example.com"}
    author = payloads.user(7, "user7")
    update = payloads.message(100, 30, 10, author, "see https://example.com", embeds=[preview])

    await scene.parse("MESSAGE_UPDATE", update)  # Discord's link preview
    await scene.edit(100, 30, "see https://example.com")  # a pin, or suppressed embeds

    # An update that keeps the text posts nothing and keeps the stored text.
    assert scene.posts(5) == []
    assert await scene.rows() == [(100, 10, 30, 7, "see https://example.com", 0)]


async def test_not_stored(scene: Scene) -> None:
    """Requirement: Edits of stored messages are logged."""
    await scene.listen(5, [30])

    await scene.edit(100, 30, "hi")  # sent before it could be stored

    assert scene.posts(5) == []
    assert await scene.rows() == []  # an edit stores nothing new


async def test_not_detected(scene: Scene) -> None:
    """Requirement: Edits of stored messages are logged."""
    await scene.listen(5, [32])
    await scene.send(100, 30, "hello")

    await scene.edit(100, 30, "hi")

    assert scene.posts(5) == []
    assert await scene.rows() == [(100, 10, 30, 7, "hi", 1)]


async def test_thread(scene: Scene) -> None:
    """Requirement: Edits of stored messages are logged."""
    await scene.listen(5, [30])  # thread 41's channel
    await scene.send(100, 41, "hello")

    await scene.edit(100, 41, "hi")

    # A thread's edits are posted.
    [post] = scene.posts(5)
    assert values(post)[:3] == ["<@7>", "<#20>", "<#41>"]
    assert post["url"] == "https://discord.com/channels/10/41/100"


async def test_channel_without_a_category(scene: Scene) -> None:
    """Requirement: Edits of stored messages are logged."""
    await scene.listen(5, [33])
    await scene.send(100, 33, "hello")

    await scene.edit(100, 33, "hi")

    # Outside categories, the category shows -.
    [post] = scene.posts(5)
    assert values(post)[:3] == ["<@7>", "-", "<#33>"]


async def test_webhook(scene: Scene) -> None:
    """Requirement: Edits of stored messages are logged."""
    await scene.listen(5, [30])
    webhook = payloads.user(500, "hook", bot=True)
    for event, text in (("MESSAGE_CREATE", "hello"), ("MESSAGE_UPDATE", "hi")):
        await scene.parse(event, payloads.message(100, 30, 10, webhook, text, webhook_id=500))

    # A webhook's edit names the webhook.
    [post] = scene.posts(5)
    assert values(post)[0] == "<@500>"
    assert "thumbnail" not in post


async def test_the_bots_own_edit(scene: Scene) -> None:
    """Requirement: Edits of stored messages are logged."""
    await scene.listen(5, [30])

    await scene.edit(100, 30, "hi", author=BOT_USER.id)

    assert scene.posts(5) == []


async def test_typed_placeholders(scene: Scene) -> None:
    """Requirement: Logged texts are shown as written and fit an embed field."""
    await scene.listen(5, [30])
    await scene.send(100, 30, "%bot_id% %cl_msg_after%")

    await scene.edit(100, 30, "%user_mention%")

    # Placeholders in a message's text are shown as written.
    [post] = scene.posts(5)
    assert values(post)[4:] == ["%bot_id% %cl_msg_after%", "%user_mention%"]


@pytest.mark.parametrize("config", ["log_all: true\n", "log_all: false\n"])
async def test_edited_at_once(scene: Scene) -> None:
    """Requirement: Edits of stored messages are logged."""
    await scene.listen(5, [30])
    author = payloads.user(7, "user7")

    # discord.py parses the frames that arrived together before any listener runs; its cached
    # message, which on_message gets, takes the edit in place.
    await burst(
        scene.bot,
        [
            ("MESSAGE_CREATE", payloads.message(100, 30, 10, author, "Loading...")),
            ("MESSAGE_UPDATE", payloads.message(100, 30, 10, author, "result")),
        ],
    )

    [post] = scene.posts(5)
    assert values(post)[3:] == ["1", "Loading...", "result"]
    assert await scene.rows() == [(100, 10, 30, 7, "result", 1)]


async def test_rich_link_preview(scene: Scene) -> None:
    """Requirement: Edits of stored messages are logged."""
    await scene.listen(5, [30])
    author = payloads.user(7, "user7")
    link = "https://x.example/status/1"
    await scene.parse("MESSAGE_CREATE", payloads.message(100, 30, 10, author, link))
    # Some previews come as rich embeds; members cannot send embeds, so theirs are previews.
    preview: payloads.Payload = {"type": "rich", "title": "A post", "description": "Its text"}

    await scene.parse(
        "MESSAGE_UPDATE", payloads.message(100, 30, 10, author, link, embeds=[preview])
    )

    assert scene.posts(5) == []
    assert await scene.rows() == [(100, 10, 30, 7, link, 0)]
