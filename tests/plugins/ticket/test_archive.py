"""The archive: the ticket's messages copied by a webhook into a thread of the chosen channel.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:360-376
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:378-516
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:690-717
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:756-782
"""

import io
import logging
import re
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING, cast

import discord
import pytest

from discord_fakes import (
    FakeAsset,
    FakeChannel,
    FakeGuild,
    FakeMember,
    FakeRole,
    FakeUser,
    forbidden,
    not_found,
    server_error,
)
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
    """The archive thread, which records each deletion asked into ``sent``."""

    id: int
    sent: list[Sent]
    delete_error: Exception | None = None

    @property
    def mention(self) -> str:
        """The mention markup."""
        return f"<#{self.id}>"

    async def delete(self) -> None:
        """Record the deletion, then raise ``delete_error`` if set."""
        self.sent.append(("thread.delete", {"id": self.id}))
        if self.delete_error is not None:
            raise self.delete_error


@dataclass
class Webhook:
    """The archive webhook, which records its sends and each deletion asked into ``sent``.

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
        """Record the deletion, then raise ``delete_error`` if set."""
        self.sent.append(("webhook.delete", {}))
        if self.delete_error is not None:
            raise self.delete_error


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


MARKERS = GOLDEN["archive"]
# The times of the thread's start and of its messages; the snowflakes hold them.
STARTED = discord.utils.time_snowflake(datetime(2026, 2, 28, 1, 0, tzinfo=UTC))
FIRST = discord.utils.time_snowflake(datetime(2026, 2, 28, 1, 30, tzinfo=UTC))
LAST = discord.utils.time_snowflake(datetime(2026, 2, 28, 1, 45, tzinfo=UTC))


def marker(text: str) -> dict[str, object]:
    """A marker in the archive thread, under the webhook's own name and avatar, as v3."""
    return {
        "content": text,
        "username": None,
        "avatar_url": None,
        "files": [],
        "mentions": NO_PINGS,
        "thread": ARCHIVE,
        "wait": True,
    }


def started(*messages: Message, error: Exception | None = None) -> Thread:
    """Thread "question" of member 8 (Bobby, cached), started at 01:00 with ``messages``."""
    return Thread(STARTED, owner=BOB, messages=list(messages), error=error)


async def test_a_started_thread(cog: Ticket) -> None:
    """Requirement: Threads started in the ticket are flattened."""
    thread = started(Message(FIRST, ALICE, "first"), Message(LAST, BOB, "second"))
    source, target = channels([Message(1, BOB, "look", thread=thread), Message(2, ALICE, "next")])

    await archive(source, target, options(cog))

    assert sends(target.sent) == [
        forwarded("look", "Bobby", BOB_AVATAR),
        marker(MARKERS["start"]),
        forwarded("first", "alice", ALICE_AVATAR),
        forwarded("second", "Bobby", BOB_AVATAR),
        marker(MARKERS["end"]),
        forwarded("next", "alice", ALICE_AVATAR),
    ]


async def test_flattened_once(cog: Ticket) -> None:
    """Requirement: Threads started in the ticket are flattened."""
    # The last message counts for the end marker, though it holds an embed only.
    thread = started(Message(FIRST, BOB, "first"), Message(LAST, ALICE))
    source, target = channels(
        [
            Message(1, BOB, thread=thread),  # its own embed only: the thread is still flattened
            Message(2, BOB, "again", thread=thread),
        ]
    )

    await archive(source, target, options(cog))

    assert sends(target.sent) == [
        marker(MARKERS["start"]),
        forwarded("first", "Bobby", BOB_AVATAR),
        marker(MARKERS["end"]),
        forwarded("again", "Bobby", BOB_AVATAR),
    ]


async def test_threads_in_threads(cog: Ticket) -> None:
    """Requirement: Threads started in the ticket are flattened."""
    inner = started(Message(FIRST, ALICE, "deeper"))
    thread = Thread(STARTED, owner=None, messages=[Message(LAST, BOB, "inside", thread=inner)])
    source, target = channels([Message(1, BOB, "look", thread=thread)])

    await archive(source, target, options(cog))

    # A thread's own threads stay as they are; an owner whom discord.py has not cached shows as
    # their ID, as v3.
    assert sends(target.sent) == [
        forwarded("look", "Bobby", BOB_AVATAR),
        marker(MARKERS["start-by-id"]),
        forwarded("inside", "Bobby", BOB_AVATAR),
        marker(MARKERS["end-by-id"]),
    ]


async def test_a_thread_without_messages(cog: Ticket) -> None:
    """Requirement: Threads started in the ticket are flattened."""
    source, target = channels([Message(1, BOB, "look", thread=started())])

    await archive(source, target, options(cog))

    assert sends(target.sent)[1:] == [
        marker(MARKERS["start"]),
        marker(MARKERS["end-without-messages"]),
    ]


@pytest.mark.parametrize("read", [0, 1], ids=["at-once", "after-a-message"])
async def test_a_thread_that_fails(cog: Ticket, read: int) -> None:
    """Requirement: Threads started in the ticket are flattened."""
    messages = [Message(FIRST, ALICE, "first")][:read]
    thread = started(*messages, error=forbidden())
    source, target = channels([Message(1, BOB, "look", thread=thread), Message(2, ALICE, "next")])

    await archive(source, target, options(cog))

    # The error marker and the end marker without a time; the archive goes on, as v3.
    assert sends(target.sent) == [
        forwarded("look", "Bobby", BOB_AVATAR),
        marker(MARKERS["start"]),
        *[forwarded("first", "alice", ALICE_AVATAR)][:read],
        marker(MARKERS["error"]),
        marker(MARKERS["end-without-messages"]),
        forwarded("next", "alice", ALICE_AVATAR),
    ]


async def test_a_refused_start_marker(cog: Ticket) -> None:
    """Requirement: Threads started in the ticket are flattened."""
    thread = started(Message(FIRST, ALICE, "first"))
    source, target = channels([Message(1, BOB, "look", thread=thread)])
    target.refused = {MARKERS["start"]: forbidden()}

    await archive(source, target, options(cog))

    assert sends(target.sent)[1:] == [
        marker(MARKERS["error"]),
        marker(MARKERS["end-without-messages"]),
    ]


async def test_a_refused_error_marker(cog: Ticket, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Threads started in the ticket are flattened."""
    thread = started(error=forbidden())
    source, target = channels([Message(1, BOB, "look", thread=thread)])
    target.refused = {MARKERS["error"]: server_error()}

    with caplog.at_level(logging.WARNING):
        await archive(source, target, options(cog))

    # Logged, and the end marker still goes, as v3.
    assert sends(target.sent)[1:] == [
        marker(MARKERS["start"]),
        marker(MARKERS["end-without-messages"]),
    ]
    assert f"Ticket cannot mark the failure of thread {STARTED} in thread {ARCHIVE}" in caplog.text


def methods(sent: list[Sent]) -> list[str]:
    """What the archive asked of Discord, in order."""
    return [method for method, _ in sent]


async def test_refused_send(cog: Ticket) -> None:
    """Requirement: A failed archive is reported and cleans up."""
    source, target = channels(
        [Message(1, BOB, "kept"), Message(2, BOB, "refused"), Message(3, BOB, "never")]
    )
    target.refused = {"refused": forbidden()}

    with pytest.raises(discord.Forbidden):
        await archive(source, target, options(cog))

    # The thread keeps what was sent; the webhook goes (v3 leaked it on some failures, B12).
    assert sends(target.sent) == [forwarded("kept", "Bobby", BOB_AVATAR)]
    assert target.sent[-1] == ("webhook.delete", {})


@pytest.mark.parametrize("refused", [False, True], ids=["deleted", "refused"])
async def test_no_webhook(cog: Ticket, refused: bool) -> None:  # noqa: FBT001
    """Requirement: A failed archive is reported and cleans up."""
    source, target = channels([Message(1, BOB, "lost")])
    target.webhook_error = forbidden()
    target.thread_delete_error = server_error() if refused else None

    # The webhook's error, not the deletion's.
    with pytest.raises(discord.Forbidden):
        await archive(source, target, options(cog))

    # The empty thread goes (v3 left it); a refused deletion changes nothing more.
    assert methods(target.sent) == ["channel.create_thread", "thread.delete"]


async def test_undeletable_webhook(cog: Ticket) -> None:
    """Requirement: A failed archive is reported and cleans up."""
    source, target = channels([Message(1, BOB, "kept")])
    target.webhook_delete_error = server_error()

    thread = await archive(source, target, options(cog))

    assert thread.id == ARCHIVE  # the archive is whole: the error is ignored, as v3's
    assert methods(target.sent)[-1] == "webhook.delete"


async def test_refused_end_marker(cog: Ticket) -> None:
    """Requirement: A failed archive is reported and cleans up."""
    thread = started(Message(LAST, BOB, "inside"))
    source, target = channels([Message(1, BOB, "look", thread=thread), Message(2, BOB, "never")])
    target.refused = {MARKERS["end"]: forbidden()}

    with pytest.raises(discord.Forbidden):
        await archive(source, target, options(cog))

    # It stops the archive, as in v3.
    assert sends(target.sent)[-1] == forwarded("inside", "Bobby", BOB_AVATAR)
    assert target.sent[-1] == ("webhook.delete", {})


REFUSED = "403 Forbidden (error code: 0): Missing Permissions"


@pytest.mark.parametrize(
    ("step", "locale", "failed"),
    [
        ("send", "en-US", "Saving failed: %tt@error%"),
        ("webhook", "en-US", "Saving failed: %tt@error%"),
        ("thread", "en-US", "Saving failed: %tt@error%"),
        ("send", "zh-TW", GOLDEN["texts"]["zh-TW"]["save-failed"]),
    ],
    ids=["send", "webhook", "thread", "send-zh-TW"],
)
async def test_save_failed(
    scene: Scene, caplog: pytest.LogCaptureFixture, step: str, locale: str, failed: str
) -> None:
    """Requirement: A failed archive is reported and cleans up."""
    target = await saving(scene, [Message(1, BOB, "help me")])
    if step == "send":
        target.refused = {"help": forbidden()}
    elif step == "webhook":
        target.webhook_error = forbidden()
    else:
        target.thread_error = forbidden()
    selection = scene.selection(SELECT, [str(TARGET)], scene.who(locale=locale))

    with caplog.at_level(logging.WARNING):
        interaction = await scene.handle(selection)

    assert interaction.sent[-1] == (
        "edit_original_response",
        {"content": failed.replace("%tt@error%", REFUSED)},
    )
    assert len(interaction.sent) == 3  # deferred, saving, failed
    assert f"Ticket cannot save channel 5 into channel 6: {REFUSED}" in caplog.text


async def test_readable_errors(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: A failed archive is reported and cleans up."""
    target = await saving(scene, [Message(1, BOB, "help me")])
    url = "https://discord.com/api/v10/webhooks/1/SECRET?wait=true"
    target.refused = {"help": OSError(f"Cannot write to {url}\n" + "x" * 300)}

    with caplog.at_level(logging.WARNING):
        interaction = await scene.handle(scene.selection(SELECT, [str(TARGET)]))

    # One line, the URL cut to its origin (its path holds the webhook's token), 200 at most.
    shown = ("Cannot write to https://discord.com " + "x" * 300)[:200]
    assert interaction.sent[-1] == (
        "edit_original_response",
        {"content": f"Saving failed: {shown}"},
    )
    # Not Discord's refusal: the traceback is logged, redacted too.
    assert "Traceback" in caplog.text
    assert "SECRET" not in caplog.text


async def test_answer_after_fifteen_minutes(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: A failed archive is reported and cleans up."""
    target = await saving(scene, [Message(1, BOB, "help me")])
    selection = scene.selection(SELECT, [str(TARGET)])
    selection.edit_errors = [None, not_found("Unknown Webhook")]  # the token has expired

    with caplog.at_level(logging.WARNING):
        await scene.handle(selection)

    assert target.sent[-1] == ("webhook.delete", {})
    assert "Ticket cannot tell member 7 how saving channel 5 went" in caplog.text
