"""Confirming a draft: v3's checks of the draft and of Administrator, then the post.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:247-295
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepData.kt:47-59
"""

import asyncio
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

import discord
import pytest

from discord_fakes import FakeChannel, FakeMessage, forbidden
from plugin_fakes import WAIT, golden
from xincord.plugins.giveaway.model import Draft, Instance, Prize, new_id
from xincord.plugins.giveaway.store import Giveaways

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import FakeInteraction

GOLDEN = golden("giveaway")
POSTS = "Confirming posts the giveaway"
FAILS = "A giveaway that cannot be posted keeps the builder"
ID = re.compile(r"[0-9a-f]{16}")
NOW = 1772244000  # the tests' clock
COMPLETE = Draft(title="Nitro", end_at=NOW + 3600, prizes=(Prize("Nitro", 1),))


def replied(interaction: FakeInteraction) -> object:
    """The interaction's only response, an ephemeral reply's text."""
    [(method, fields)] = interaction.sent
    assert method == "response.send_message"
    assert fields["ephemeral"] is True
    return fields["content"]


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


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_not_an_administrator(scene: Scene, locale: str) -> None:
    """Requirement: Confirming checks the draft and the administrator."""
    scene.keep(COMPLETE)

    pressed = await scene.press("confirm-create", scene.who(locale=locale, admin=False))

    assert replied(pressed) == GOLDEN["replies"][locale]["not-admin"]
    assert scene.draft() == COMPLETE


@dataclass
class GatedChannel(FakeChannel):
    """A channel whose ``send`` sets ``sending`` and waits for ``gate`` before it records."""

    gate: asyncio.Event = field(default_factory=asyncio.Event)
    sending: asyncio.Event = field(default_factory=asyncio.Event)

    async def send(self, **fields: object) -> FakeMessage:
        """Wait for the gate, then record the message."""
        self.sending.set()
        await self.gate.wait()
        return await super().send(**fields)


async def until_sending(channel: GatedChannel, task: asyncio.Task[FakeInteraction]) -> None:
    """Wait until the channel sends, or until the press ended, whose error is raised then."""
    waiting = asyncio.create_task(channel.sending.wait())
    done, _ = await asyncio.wait({waiting, task}, timeout=WAIT, return_when=asyncio.FIRST_COMPLETED)
    waiting.cancel()
    for finished in done:
        finished.result()


def posts(scene: Scene) -> list[dict[str, object]]:
    """The messages that the builder's channel got."""
    channel = cast("FakeChannel", scene.channel)
    return [fields for method, fields in channel.sent if method == "channel.send"]


def giveaway_id(post: dict[str, object]) -> str:
    """The giveaway ID in the IDs of a post's buttons."""
    view = post["view"]
    assert isinstance(view, discord.ui.View)
    first = view.children[0]
    assert isinstance(first, discord.ui.Button)
    custom_id = str(first.custom_id)
    assert custom_id.startswith("giveaway:1:a=participate;c=")
    return custom_id.rpartition("=")[2]


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=POSTS)
@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_posted(scene: Scene, locale: str) -> None:
    """Requirement: Confirming posts the giveaway."""
    scene.keep(COMPLETE)

    pressed = await scene.press("confirm-create", scene.who(locale=locale))

    [post] = posts(scene)
    found = giveaway_id(post)
    assert ID.fullmatch(found)
    stored = await Giveaways(scene.store).get(10, found)
    expected = Instance(found, 10, 5, 500, 7, COMPLETE, locale_tag=locale, created_at=NOW)
    assert stored == expected
    deferred, (method, finished) = pressed.sent
    assert deferred == ("response.defer", {})  # v3's deferEdit
    assert method == "edit_original_response"
    link = "https://discord.com/channels/10/5/500"
    assert finished == {
        "content": GOLDEN["created"][locale] + link,
        "embeds": (),
        "view": None,
        "attachments": (),
    }
    assert scene.cog.drafts == {}


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=POSTS)
async def test_post_is_the_template(scene: Scene) -> None:
    """Requirement: Confirming posts the giveaway."""
    scene.keep(COMPLETE)

    await scene.press("confirm-create")

    [post] = posts(scene)
    found = giveaway_id(post)
    instance = await Giveaways(scene.store).get(10, found)
    assert instance is not None
    message = scene.cog.render_post(instance)
    assert post["content"] is None
    assert post["embeds"] == message.embeds
    assert post["files"] == ()


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=POSTS)
async def test_double_press(scene: Scene) -> None:
    """Requirement: Confirming posts the giveaway."""
    channel = GatedChannel(id=5)
    scene.channel = channel
    scene.keep(COMPLETE)

    first = asyncio.create_task(scene.press("confirm-create"))
    await until_sending(channel, first)
    second = await scene.press("confirm-create")  # while the first one posts
    channel.gate.set()
    await first

    assert replied(second) == GOLDEN["replies"]["en-US"]["expired"]
    assert len(posts(scene)) == 1
    assert len(await Giveaways(scene.store).ids(10)) == 1


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=POSTS)
def test_new_ids() -> None:
    """Requirement: Confirming posts the giveaway."""
    hexes = iter(["aaaaaaaaaaaaaaaa" + "1" * 16, "bbbbbbbbbbbbbbbb" + "2" * 16])

    assert new_id({"aaaaaaaaaaaaaaaa"}, lambda: next(hexes)) == "bbbbbbbbbbbbbbbb"


def failure(interaction: FakeInteraction) -> str:
    """The text of the ephemeral follow-up after the deferral, the interaction's responses."""
    deferred, (method, fields) = interaction.sent
    assert deferred == ("response.defer", {})
    assert method == "followup.send"
    assert fields["ephemeral"] is True
    return str(fields["content"])


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=FAILS)
@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_channel_refuses(scene: Scene, locale: str, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: A giveaway that cannot be posted keeps the builder."""
    scene.channel = FakeChannel(id=5, error=forbidden())
    scene.keep(COMPLETE)

    with caplog.at_level(logging.WARNING):
        pressed = await scene.press("confirm-create", scene.who(locale=locale))

    text = failure(pressed)
    assert text.startswith(GOLDEN["failed"][locale])
    assert "Missing Permissions" in text  # v3's %ga@error% was the exception's message
    assert scene.draft() == COMPLETE  # given back; the builder stays
    assert await Giveaways(scene.store).ids(10) == frozenset()
    assert "Giveaway cannot post a giveaway in channel 5 of guild 10" in caplog.text

    scene.channel = FakeChannel(id=5)  # the permission is back
    await scene.press("confirm-create")
    assert len(posts(scene)) == 1


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=FAILS)
async def test_channel_takes_no_messages(scene: Scene) -> None:
    """Requirement: A giveaway that cannot be posted keeps the builder."""
    scene.channel = object()  # as a category: no send
    scene.keep(COMPLETE)

    pressed = await scene.press("confirm-create")

    assert failure(pressed) == GOLDEN["failed"]["en-US"] + "the channel takes no messages"
    assert scene.draft() == COMPLETE


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=FAILS)
async def test_store_fails(scene: Scene, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement: A giveaway that cannot be posted keeps the builder."""
    scene.keep(COMPLETE)

    async def add(_giveaways: Giveaways, instance: Instance) -> None:
        del instance
        message = "database is locked"
        raise sqlite3.OperationalError(message)

    monkeypatch.setattr(Giveaways, "add", add)
    pressed = await scene.press("confirm-create")

    channel = cast("FakeChannel", scene.channel)
    assert [method for method, _ in channel.sent] == ["channel.send", "message.delete"]
    assert failure(pressed) == GOLDEN["failed"]["en-US"] + "database is locked"
    assert scene.draft() == COMPLETE


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=FAILS)
async def test_new_draft_while_posting(scene: Scene) -> None:
    """Requirement: A giveaway that cannot be posted keeps the builder."""
    channel = GatedChannel(id=5, error=forbidden())
    scene.channel = channel
    scene.keep(COMPLETE)

    pressed = asyncio.create_task(scene.press("confirm-create"))
    await until_sending(channel, pressed)
    scene.keep(Draft(title="Newer"), scene.who(message_id=44))
    channel.gate.set()
    await pressed

    assert scene.draft() == Draft(title="Newer")  # the failed draft does not replace it
