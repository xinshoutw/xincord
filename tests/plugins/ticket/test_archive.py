"""The archive: the ticket's messages copied by a webhook into a thread of the chosen channel.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:360-376
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:378-516
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:690-717
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:756-782
"""

import io
import re
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING, cast

import discord
import pytest

from discord_fakes import FakeAsset, FakeChannel, FakeGuild, FakeMember, FakeRole, FakeUser
from plugin_fakes import golden
from xincord.plugins.ticket.archive import (
    Options,
    archive,
    forwarded_name,
    thread_name,
    webhook_name,
)
from xincord.plugins.ticket.cog import IDS
from xincord.plugins.ticket.store import NAMESPACE

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from conftest import Scene
    from discord_fakes import Sent
    from xincord.plugins.ticket.cog import Ticket

GOLDEN = golden("ticket")
NOW = 1772244000.0  # 2026-02-28 02:00:00 UTC, when the archive starts
LIMIT = 1000  # the guild's upload limit in these tests, in bytes
ARCHIVE = 800  # the archive thread's ID
WEBHOOK = re.compile(r"ticket-save-content-mm5obi80-[0-9a-z]{1,4}")  # base36 of NOW in ms
NO_PINGS: dict[str, list[str]] = {"parse": []}  # allowed mentions that ping nobody
BOB_AVATAR = "https://cdn.example/bob.png"
ALICE_AVATAR = "https://cdn.example/alice.png"
# A member whom discord.py has, and a user whom it has not cached as a member.
BOB = FakeMember(FakeGuild(10), id=8, name="bob", nick="Bobby", guild_avatar=FakeAsset(BOB_AVATAR))
ALICE = FakeUser(id=7, name="alice", global_name="Alice", avatar=FakeAsset(ALICE_AVATAR))
PANEL = "500"
TARGET = 6  # the text channel that the archive goes into
SELECT = IDS.build(
    {
        "action": "save",
        "sub_action": "select-channel",
        "user_id": "8",
        "msg_id": PANEL,
        "btn_index": "0",
    }
)


@dataclass
class Attached:
    """A message's file; its URL comes from its name."""

    filename: str
    size: int = 10

    @property
    def url(self) -> str:
        """The file's URL."""
        return f"https://cdn.discordapp.com/attachments/5/1/{self.filename}"

    async def to_file(self) -> discord.File:
        """The file, as discord.py downloads it."""
        return discord.File(io.BytesIO(b"data"), filename=self.filename)


@dataclass
class Message:
    """A message of the ticket's history, or of a thread's."""

    id: int
    author: FakeMember | FakeUser
    content: str = ""
    attachments: list[Attached] = field(default_factory=list[Attached])
    thread: Thread | None = None  # the thread that the message started


@dataclass
class Thread:
    """A thread that a message started; reading its messages fails with ``error`` after them."""

    id: int
    name: str = "question"
    owner_id: int = 8
    owner: FakeMember | None = None  # when discord.py has the member
    messages: list[Message] = field(default_factory=list[Message])
    error: Exception | None = None

    async def history(self, *, limit: int | None, oldest_first: bool) -> AsyncIterator[Message]:
        """The thread's messages, oldest first, as discord.py pages them."""
        assert limit is None
        assert oldest_first
        for message in self.messages:
            yield message
        if self.error is not None:
            raise self.error


@dataclass
class Created:
    """The archive thread, which records its deletion into ``sent``."""

    id: int
    sent: list[Sent]
    delete_error: Exception | None = None

    @property
    def mention(self) -> str:
        """The mention markup."""
        return f"<#{self.id}>"

    async def delete(self) -> None:
        """Record the deletion, or raise ``delete_error``."""
        if self.delete_error is not None:
            raise self.delete_error
        self.sent.append(("thread.delete", {"id": self.id}))


@dataclass
class Webhook:
    """The archive webhook, which records its sends and its deletion into ``sent``.

    A send whose text holds a key of ``refused`` raises that key's error.
    """

    name: str
    sent: list[Sent]
    refused: dict[str, Exception]
    delete_error: Exception | None = None

    async def send(  # noqa: PLR0913 - discord.py's keywords
        self,
        content: str | None = None,
        *,
        username: str | None = None,
        avatar_url: str | None = None,
        files: Sequence[discord.File] = (),
        allowed_mentions: discord.AllowedMentions | None = None,
        thread: object = None,
        wait: bool = False,
    ) -> None:
        """Record a message sent to ``thread``, or raise the error of a refused text."""
        for part, error in self.refused.items():
            if part in (content or ""):
                raise error
        mentions = None if allowed_mentions is None else allowed_mentions.to_dict()
        fields: dict[str, object] = {
            "content": content,
            "username": username,
            "avatar_url": avatar_url,
            "files": [file.filename for file in files],
            "mentions": mentions,
            "thread": getattr(thread, "id", None),
            "wait": wait,
        }
        self.sent.append(("webhook.send", fields))

    async def delete(self) -> None:
        """Record the deletion, or raise ``delete_error``."""
        if self.delete_error is not None:
            raise self.delete_error
        self.sent.append(("webhook.delete", {}))


@dataclass
class Channel(FakeChannel):
    """A text channel with its messages, where threads and webhooks are made.

    The errors make the creations, the webhook's refused sends and the deletions fail.
    """

    history_messages: list[Message] = field(default_factory=list[Message])
    thread_error: Exception | None = None
    webhook_error: Exception | None = None
    refused: dict[str, Exception] = field(default_factory=dict[str, Exception])
    thread_delete_error: Exception | None = None
    webhook_delete_error: Exception | None = None

    async def history(self, *, limit: int | None, oldest_first: bool) -> AsyncIterator[Message]:
        """The channel's messages, oldest first, as discord.py pages them."""
        assert limit is None
        assert oldest_first
        for message in self.history_messages:
            yield message

    async def create_thread(
        self,
        *,
        name: str,
        type: discord.ChannelType,  # noqa: A002 - discord.py's name
    ) -> Created:
        """Record the thread's creation and return it."""
        if self.thread_error is not None:
            raise self.thread_error
        self.sent.append(("channel.create_thread", {"name": name, "type": type}))
        return Created(ARCHIVE, self.sent, self.thread_delete_error)

    async def create_webhook(self, *, name: str) -> Webhook:
        """Record the webhook's creation and return it."""
        if self.webhook_error is not None:
            raise self.webhook_error
        self.sent.append(("channel.create_webhook", {"name": name}))
        return Webhook(name, self.sent, self.refused, self.webhook_delete_error)


def channels(history: Sequence[Message]) -> tuple[Channel, Channel]:
    """Ticket channel 5, named bob, with ``history``, and channel 6 to archive it in, which
    record into one list."""
    source = Channel(id=5, name="bob", history_messages=list(history))
    return source, Channel(sent=source.sent, id=TARGET, name="archive")


def options(cog: Ticket) -> Options:
    """The archive's texts in zh-TW, its start, the zone UTC and an upload limit of 1000 bytes."""
    return Options(cog.public, NOW, UTC, LIMIT)


def sends(sent: list[Sent]) -> list[dict[str, object]]:
    """What the webhook sent, in order."""
    return [fields for method, fields in sent if method == "webhook.send"]


def forwarded(
    content: str | None, name: str, avatar: str, files: Sequence[str] = ()
) -> dict[str, object]:
    """A message forwarded into the archive thread under its author's name and avatar."""
    return {
        "content": content,
        "username": name,
        "avatar_url": avatar,
        "files": list(files),
        "mentions": NO_PINGS,
        "thread": ARCHIVE,
        "wait": True,
    }


async def saving(scene: Scene, history: Sequence[Message]) -> Channel:
    """Guild 10's ticket channel 5 with ``history``, its stored entry and channel 6 to save into,
    with the cog's clock and zone fixed."""
    scene.guild.roles.append(FakeRole(3))
    await scene.store.put(
        NAMESPACE, "10", {PANEL: [{"reasonTitle": "Why?", "adminIds": [3], "categoryId": 0}]}
    )
    source, target = channels(history)
    scene.channel = source
    scene.guild.channels.append(target)
    scene.cog.clock = lambda: NOW
    scene.cog.zone = UTC
    return target


async def test_forwarded_messages(cog: Ticket) -> None:
    """Requirement: The archive copies the conversation into a thread."""
    source, target = channels(
        [
            Message(1, BOB, "help me"),
            Message(2, ALICE),  # an embed only, or a sticker: skipped, as in v3
            Message(3, ALICE, attachments=[Attached("log.txt")]),
        ]
    )

    thread = await archive(source, target, options(cog))

    assert thread.mention == f"<#{ARCHIVE}>"
    created, webhook, *rest = target.sent
    assert created == (
        "channel.create_thread",
        {"name": "bob-2026-02-28_02:00:00", "type": discord.ChannelType.public_thread},
    )
    assert webhook[0] == "channel.create_webhook"
    assert WEBHOOK.fullmatch(cast("str", webhook[1]["name"]))
    # The member under their display name, the user under their username, as v3.
    assert rest == [
        ("webhook.send", forwarded("help me", "Bobby", BOB_AVATAR)),
        ("webhook.send", forwarded(None, "alice", ALICE_AVATAR, ["log.txt"])),
        ("webhook.delete", {}),
    ]


async def test_long_messages_and_large_files(cog: Ticket) -> None:
    """Requirement: The archive copies the conversation into a thread."""
    large, small = Attached("video.mp4", size=LIMIT + 1), Attached("log.txt", size=LIMIT)
    source, target = channels(
        [
            Message(1, BOB, "x" * 3900, [large, small]),
            Message(2, BOB, "y" * 4000, [small]),
            Message(3, BOB, attachments=[large]),
        ]
    )

    await archive(source, target, options(cog))

    # Parts of 2000, the files with the last (v3 hung, B12); a file over the guild's upload
    # limit is linked on its own line (v3's upload failed).
    assert sends(target.sent) == [
        forwarded("x" * 2000, "Bobby", BOB_AVATAR),
        forwarded("x" * 1900 + "\n" + large.url, "Bobby", BOB_AVATAR, ["log.txt"]),
        forwarded("y" * 2000, "Bobby", BOB_AVATAR),
        forwarded("y" * 2000, "Bobby", BOB_AVATAR, ["log.txt"]),
        forwarded(large.url, "Bobby", BOB_AVATAR),
    ]


async def test_names_discord_refuses(cog: Ticket) -> None:
    """Requirement: The archive copies the conversation into a thread."""
    source, target = channels(
        [
            Message(1, replace(BOB, nick="Discord Fan"), "a"),
            Message(2, replace(BOB, nick="discord", name="clyde"), "b"),
        ]
    )

    await archive(source, target, options(cog))

    # v3's archive failed there.
    assert [fields["username"] for fields in sends(target.sent)] == ["bob", "8"]


@pytest.mark.parametrize(
    ("author", "expected"),
    [
        (BOB, "Bobby"),
        (replace(BOB, nick="  Bobby  "), "Bobby"),
        (replace(BOB, nick="y" * 80), "y" * 80),
        (replace(BOB, nick="y" * 81), "bob"),
        (replace(BOB, nick="   "), "bob"),
        (replace(BOB, nick="I like Discord"), "bob"),
        (replace(BOB, nick="CLYDE"), "bob"),
        (replace(BOB, nick="a@b"), "bob"),
        (replace(BOB, nick="#1"), "bob"),
        (replace(BOB, nick="a:b"), "bob"),
        (replace(BOB, nick="a```b"), "bob"),
        (replace(BOB, nick="Everyone"), "bob"),
        (replace(BOB, nick="here"), "bob"),
        (replace(BOB, nick="discord", name="clyde"), "8"),
        (ALICE, "alice"),  # no member: the username, as v3's author.name
        (replace(ALICE, name="discordian"), "7"),
    ],
)
def test_forwarded_name(author: FakeMember | FakeUser, expected: str) -> None:
    """Requirement: The archive copies the conversation into a thread."""
    assert forwarded_name(author) == expected


SUFFIX = "-2026-02-28_02:00:00"
ACUTE = chr(0x301)  # a combining mark
KEYCAP = chr(0x20E3)  # an enclosing mark
ZWJ = chr(0x200D)
MAN = chr(0x1F468)  # two UTF-16 code units, as each character outside the BMP
HEART, VS16 = chr(0x2764), chr(0xFE0F)
THUMBS, TONE = chr(0x1F44D), chr(0x1F3FD)


@pytest.mark.parametrize(
    ("name", "kept"),
    [
        ("bob", "bob"),
        ("x" * 80, "x" * 80),
        ("x" * 81, "x" * 80),
        ("x" * 79 + MAN, "x" * 79),  # a surrogate pair stays whole
        ("x" * 79 + "e" + ACUTE + "z", "x" * 79),
        ("x" * 79 + "1" + KEYCAP, "x" * 79),
        ("x" * 78 + MAN + ZWJ + MAN, "x" * 78),
        ("x" * 79 + ZWJ + "y", "x" * 78),
        ("x" * 79 + HEART + VS16, "x" * 79),
        ("x" * 78 + THUMBS + TONE, "x" * 78),
        ("x" + ACUTE * 100, ""),  # one character too long for the name
    ],
    ids=[
        "short",
        "fits",
        "long",
        "pair",
        "combining",
        "enclosing",
        "joined",
        "joiner",
        "variation",
        "modifier",
        "cluster",
    ],
)
def test_thread_name(name: str, kept: str) -> None:
    """Requirement: The archive copies the conversation into a thread."""
    # 100 UTF-16 code units at most, the time taking 20 (v3's BreakIterator kept graphemes).
    assert thread_name(name, NOW, UTC) == kept + SUFFIX


def test_thread_name_in_a_zone() -> None:
    """Requirement: The archive copies the conversation into a thread."""
    taipei = timezone(timedelta(hours=8))
    local = datetime.fromtimestamp(NOW, UTC).astimezone().strftime("%Y-%m-%d_%H:%M:%S")

    assert thread_name("bob", NOW, taipei) == "bob-2026-02-28_10:00:00"
    assert thread_name("bob", NOW, None) == f"bob-{local}"  # the host's zone, as v3


@pytest.mark.parametrize(
    ("milliseconds", "counter", "name"),
    [
        (0, 0, "ticket-save-content-0-0"),
        (1772244000000, 0x1234567, "ticket-save-content-mm5obi80-4lev"),
        (35, 0xFFFFF, "ticket-save-content-z-mh33"),
    ],
)
def test_webhook_name(milliseconds: int, counter: int, name: str) -> None:
    """Requirement: The archive copies the conversation into a thread."""
    # Java's Long.toString(n, 36) of the time and of the counter's 20 low bits.
    assert webhook_name(milliseconds, counter) == name


@pytest.mark.parametrize(
    ("locale", "texts"),
    [
        ("en-US", {"saving": "Saving...", "saved": "Saved in the thread %tt@thread%"}),
        ("zh-TW", GOLDEN["texts"]["zh-TW"]),
    ],
    ids=["en-US", "zh-TW"],
)
async def test_saved(scene: Scene, locale: str, texts: dict[str, str]) -> None:
    """Requirement: The archive copies the conversation into a thread."""
    target = await saving(scene, [Message(1, BOB, "help me")])
    selection = scene.selection(SELECT, [str(TARGET)], scene.who(locale=locale))

    interaction = await scene.handle(selection)

    # A new ephemeral answer (v3's deferReply), so the select stays usable.
    assert interaction.sent == [
        ("response.defer", {"ephemeral": True, "thinking": True}),
        ("edit_original_response", {"content": texts["saving"]}),
        ("edit_original_response", {"content": texts["saved"].replace("%tt@thread%", "<#800>")}),
    ]
    assert target.sent[0] == (
        "channel.create_thread",
        {"name": "bob-2026-02-28_02:00:00", "type": discord.ChannelType.public_thread},
    )
    assert sends(target.sent) == [forwarded("help me", "Bobby", BOB_AVATAR)]
    assert target.sent[-1] == ("webhook.delete", {})


async def test_upload_limit_of_the_guild(scene: Scene) -> None:
    """Requirement: The archive copies the conversation into a thread."""
    large = Attached("video.mp4", size=11)
    target = await saving(scene, [Message(1, BOB, "see", [large])])
    scene.guild.filesize_limit = 10

    await scene.handle(scene.selection(SELECT, [str(TARGET)]))

    assert sends(target.sent) == [forwarded("see\n" + large.url, "Bobby", BOB_AVATAR)]
