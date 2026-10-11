"""The deletions of stored messages, alone or in bulk, posted to the detecting listen channels."""

from typing import TYPE_CHECKING

import discord
import pytest

import payloads
from discord_fakes import not_found
from plugin_fakes import burst, golden

if TYPE_CHECKING:
    from conftest import Scene

GOLDEN = golden("chat_logger")
MEMBER_REQUEST = "GET /guilds/10/members/7"


def values(post: dict[str, object]) -> list[object]:
    """The field values of a posted embed, in the template's order."""
    fields = post["fields"]
    assert isinstance(fields, list)
    return [field["value"] for field in fields]  # pyright: ignore[reportUnknownVariableType]


def fetched(scene: Scene) -> list[str]:
    """The REST requests that fetched a member."""
    return [request for request, _ in scene.rest.sent if "/members/" in request]


def member_answers(scene: Scene, count: int = 1) -> None:
    """Discord answers ``count`` fetches of member 7."""
    scene.rest.answers[MEMBER_REQUEST] = [payloads.member(7, "user7") for _ in range(count)]


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_delete(scene: Scene, locale: str) -> None:
    """Requirement: Deletions of stored messages are logged."""
    scene.guild.preferred_locale = discord.Locale(locale)
    await scene.listen(5, [30])
    await scene.send(100, 30, "hello")
    await scene.edit(100, 30, "hi")
    member_answers(scene)

    await scene.delete(100, 30)

    assert scene.posts(5)[1:] == [GOLDEN["deletion"][locale]]
    assert fetched(scene) == [MEMBER_REQUEST]  # v3's retrieveMemberById
    assert await scene.rows() == []  # v3 kept the text of deleted messages


async def test_author_gone(scene: Scene) -> None:
    """Requirement: Deletions of stored messages are logged."""
    await scene.listen(5, [30])
    await scene.send(100, 30, "hello")
    scene.rest.errors[MEMBER_REQUEST] = not_found()  # the author left the guild

    await scene.delete(100, 30)

    # v3 posted nothing: its fallback for an unknown member was dead code.
    [post] = scene.posts(5)
    assert values(post) == ["<@7>", "<#20>", "<#30>", "0", "hello"]
    assert "thumbnail" not in post


async def test_not_stored(scene: Scene) -> None:
    """Requirement: Deletions of stored messages are logged."""
    await scene.listen(5, [30])

    await scene.delete(100, 30)

    assert scene.posts(5) == []
    assert fetched(scene) == []


async def test_not_detected(scene: Scene) -> None:
    """Requirement: Deletions of stored messages are logged."""
    await scene.listen(5, [32])
    await scene.send(100, 30, "hello")

    await scene.delete(100, 30)

    assert scene.posts(5) == []
    assert fetched(scene) == []
    assert await scene.rows() == []


async def test_bulk_deletion(scene: Scene) -> None:
    """Requirement: Deletions of stored messages are logged."""
    await scene.listen(5, [20])
    for message_id, text in ((102, "third"), (100, "first"), (101, "second")):
        await scene.send(message_id, 41, text)  # in thread 41 of channel 30, category 20
    await scene.send(200, 33, "elsewhere")
    member_answers(scene)

    await scene.delete_all([101, 103, 102, 100], 41)  # 103 is not stored

    # v3 never logged a bulk deletion: JDA's splitting was off and the plugin ignored them.
    assert [values(post)[1:] for post in scene.posts(5)] == [
        ["<#20>", "<#41>", "0", "first"],
        ["<#20>", "<#41>", "0", "second"],
        ["<#20>", "<#41>", "0", "third"],
    ]
    assert fetched(scene) == [MEMBER_REQUEST]  # once for the three
    assert [row[0] for row in await scene.rows()] == [200]


async def test_long_text(scene: Scene) -> None:
    """Requirement: Logged texts are shown as written and fit an embed field."""
    await scene.listen(5, [30])
    text = "".join(f"{index:04d} " for index in range(400))  # 2000 characters
    await scene.send(100, 30, text)
    member_answers(scene)

    await scene.delete(100, 30)

    # v3 threw for a field over 1024 characters, so the deletion was not logged.
    [post] = scene.posts(5)
    content = str(values(post)[4])
    assert len(content) == 1024
    assert content == text[:1021] + "..."


async def test_outside_a_guild(scene: Scene) -> None:
    """Requirement: Deletions of stored messages are logged."""
    await scene.listen(5, [30])
    await scene.send(100, 30, "hello")

    # Deletions without a guild are direct messages', which are never stored.
    await scene.parse("MESSAGE_DELETE", {"id": "100", "channel_id": "50"})
    await scene.parse("MESSAGE_DELETE_BULK", {"ids": ["100"], "channel_id": "50"})

    assert scene.posts(5) == []
    assert [row[0] for row in await scene.rows()] == [100]


@pytest.mark.parametrize("config", ["log_all: true\n", "log_all: false\n"])
async def test_deleted_at_once(scene: Scene) -> None:
    """Requirement: Deletions of stored messages are logged."""
    await scene.listen(5, [30])
    member_answers(scene)
    author = payloads.user(7, "user7")

    # A message deleted right after it was sent, as a ghost ping: with log_all false, its insert
    # waits for the settings, and the deletion must not reach the store before it.
    await burst(
        scene.bot,
        [
            ("MESSAGE_CREATE", payloads.message(100, 30, 10, author, "@everyone")),
            ("MESSAGE_DELETE", {"id": "100", "channel_id": "30", "guild_id": "10"}),
        ],
    )

    [post] = scene.posts(5)
    assert values(post)[4] == "@everyone"
    assert await scene.rows() == []


@pytest.mark.parametrize("config", ["keep_deleted: true\n"])
async def test_kept(scene: Scene) -> None:
    """Requirement: Deleted texts can be kept."""
    await scene.listen(5, [30])
    for message_id in (100, 101, 102, 103):
        await scene.send(message_id, 30, f"text {message_id}")
    member_answers(scene, 2)

    await scene.delete(100, 30)
    await scene.delete_all([101, 102, 103], 30)

    assert [values(post)[-1] for post in scene.posts(5)] == [
        "text 100",
        "text 101",
        "text 102",
        "text 103",
    ]
    assert [row[0] for row in await scene.rows()] == [100, 101, 102, 103]


@pytest.mark.parametrize("config", ["log_all: true\n"])
async def test_removed_by_default(scene: Scene) -> None:
    """Requirement: Deleted texts can be kept."""
    await scene.listen(5, [30])
    await scene.send(100, 30, "hello")
    member_answers(scene)

    await scene.delete(100, 30)

    assert len(scene.posts(5)) == 1
    assert await scene.rows() == []
