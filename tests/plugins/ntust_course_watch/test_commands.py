"""The three commands: their registration, their changes and their replies.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/command/Register.kt:12-28
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/Event.kt:49-61
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/NtustCourse.kt:32-92
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-30
"""

from typing import TYPE_CHECKING, Any, cast

import discord
import pytest
from discord import app_commands

from discord_fakes import FakeChannel, FakeInteraction, FakeUser
from plugin_fakes import golden
from xincord.plugins.ntust_course_watch.store import KEY, NAMESPACE

if TYPE_CHECKING:
    from xincord.core.bot import Bot
    from xincord.core.command_tree import CommandTree
    from xincord.core.storage import Store
    from xincord.plugins.ntust_course_watch.cog import NtustCourseWatch

GOLDEN = golden("ntust_course_watch")
ENGLISH = GOLDEN["replies"]["en-US"]
NAMES = ("course-add", "course-remove", "course-list")


def interaction(
    user: int = 1, channel: int = 5, locale: discord.Locale = discord.Locale.american_english
) -> FakeInteraction:
    """A member's command in a guild channel, as the command tree deferred it."""
    return FakeInteraction(
        {"type": 2}, user=FakeUser(id=user), channel=FakeChannel(id=channel), locale=locale
    )


def replies(fake: FakeInteraction) -> list[str]:
    """What the plugin edited the deferred response into."""
    return [
        str(fields["content"]) for method, fields in fake.sent if method == "edit_original_response"
    ]


def listed(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """The entries of ``actual`` whose keys ``expected`` lists, options included."""
    entries = {key: actual.get(key) for key in expected if key != "options"}
    if "options" in expected:
        entries["options"] = [
            listed(option, wanted)
            for option, wanted in zip(actual.get("options", []), expected["options"], strict=False)
        ]
    return entries


async def test_command_payload(bot: Bot) -> None:
    """Requirement: Commands keep v3's names and answer in the member's locale."""
    global_payload, guild_payload = await cast("CommandTree", bot.tree).payloads()
    expected: list[dict[str, Any]] = GOLDEN["commands"]
    by_name = {entry["name"]: entry for entry in guild_payload}

    assert [listed(by_name.get(wanted["name"], {}), wanted) for wanted in expected] == expected
    assert [wanted["name"] for wanted in expected] == list(NAMES)
    assert not {entry["name"] for entry in global_payload} & set(NAMES)  # guild commands


@pytest.mark.parametrize("name", NAMES)
async def test_command_binding(bot: Bot, cog: NtustCourseWatch, name: str) -> None:
    """Requirement: Commands keep v3's names and answer in the member's locale."""
    command = bot.tree.get_command(name)

    assert isinstance(command, app_commands.Command)
    assert command.binding is cog
    assert command.extras.get("defer", True)  # the tree's ephemeral deferral, as v3's core


async def test_register(cog: NtustCourseWatch, store: Store) -> None:
    """Requirement: Members register courses in a channel."""
    fake = interaction()

    await cog.add_course(fake.as_interaction(), "CE162A001")

    assert await cog.registrations.load() == {"CE162A001": {5: (1,)}}
    assert await store.get(NAMESPACE, KEY) == {"CE162A001": {"5": ["1"]}}
    assert replies(fake) == [ENGLISH["registered"]]


async def test_register_twice(cog: NtustCourseWatch) -> None:
    """Requirement: Members register courses in a channel."""
    first, second = interaction(), interaction()

    await cog.add_course(first.as_interaction(), "CE162A001")
    await cog.add_course(second.as_interaction(), "CE162A001")

    assert await cog.registrations.load() == {"CE162A001": {5: (1,)}}  # v3 listed it twice
    assert replies(second) == [ENGLISH["registered"]]


@pytest.mark.parametrize(
    "typed",
    [
        pytest.param(" ce162a001 ", id="lower case with spaces"),
        pytest.param("Ce162A001\t", id="mixed case with a tab"),
        pytest.param("".join(chr(ord(char) + 0xFEE0) for char in "CE162A001"), id="full-width"),
    ],
)
async def test_typed_loosely(cog: NtustCourseWatch, typed: str) -> None:
    """Requirement: Members register courses in a channel."""
    fake = interaction()

    await cog.add_course(fake.as_interaction(), typed)

    # v3 stored the code as typed, and a typo of case or spaces never matched NTUST's codes.
    assert await cog.registrations.load() == {"CE162A001": {5: (1,)}}
    assert replies(fake) == [ENGLISH["registered"]]


@pytest.mark.parametrize(
    "typed",
    [
        pytest.param("CE 162", id="space inside"),
        pytest.param("CE-162", id="hyphen"),
        pytest.param("A" * 21, id="21 characters"),
        pytest.param("   ", id="blank"),
        pytest.param("CE162A001" + chr(0x4E2D), id="a Chinese character"),
        pytest.param("%ncw@course_id%", id="placeholder"),
    ],
)
async def test_invalid_code(cog: NtustCourseWatch, store: Store, typed: str) -> None:
    """Requirement: Members register courses in a channel."""
    fake = interaction()

    await cog.add_course(fake.as_interaction(), typed)

    assert await store.get(NAMESPACE, KEY) is None
    assert replies(fake) == [ENGLISH["invalid-code"]]


async def test_twenty_characters(cog: NtustCourseWatch) -> None:
    """Requirement: Members register courses in a channel."""
    fake = interaction()

    await cog.add_course(fake.as_interaction(), "A1" * 10)

    assert await cog.registrations.load() == {"A1" * 10: {5: (1,)}}


async def test_unregister(cog: NtustCourseWatch) -> None:
    """Requirement: Members unregister their own courses."""
    await cog.registrations.add("CE162A001", 5, 1)
    await cog.registrations.add("CE162A001", 5, 2)
    await cog.registrations.add("CE162A001", 6, 1)
    fake = interaction(user=1, channel=5)

    await cog.remove_course(fake.as_interaction(), "ce162a001")

    # v3 removed the channel's whole entry for the course, every member's registration with it.
    assert await cog.registrations.load() == {"CE162A001": {5: (2,), 6: (1,)}}
    assert replies(fake) == [ENGLISH["unregistered"]]


async def test_not_registered(cog: NtustCourseWatch, store: Store) -> None:
    """Requirement: Members unregister their own courses."""
    await cog.registrations.add("CE162A001", 5, 2)
    fake = interaction(user=1, channel=5)

    await cog.remove_course(fake.as_interaction(), "CE162A001")

    assert await store.get(NAMESPACE, KEY) == {"CE162A001": {"5": ["2"]}}
    assert replies(fake) == [ENGLISH["unregistered"]]  # as v3, which always said so


async def test_last_registration(cog: NtustCourseWatch, store: Store) -> None:
    """Requirement: Members unregister their own courses."""
    await cog.registrations.add("CE162A001", 5, 1)

    await cog.remove_course(interaction().as_interaction(), "CE162A001")

    assert await store.get(NAMESPACE, KEY) is None


async def test_unregister_invalid_code(cog: NtustCourseWatch, store: Store) -> None:
    """Requirement: Members unregister their own courses."""
    await cog.registrations.add("CE162A001", 5, 1)
    fake = interaction()

    await cog.remove_course(fake.as_interaction(), "CE-162")

    assert await store.get(NAMESPACE, KEY) == {"CE162A001": {"5": ["1"]}}
    assert replies(fake) == [ENGLISH["invalid-code"]]


async def test_list(cog: NtustCourseWatch) -> None:
    """Requirement: Members list their courses in the channel."""
    await cog.registrations.add("CE162A002", 5, 1)
    await cog.registrations.add("CE162A001", 5, 1)
    await cog.registrations.add("CE162A003", 6, 1)
    await cog.registrations.add("CE162A004", 5, 2)
    fake = interaction(user=1, channel=5)

    await cog.list_courses(fake.as_interaction())

    assert replies(fake) == [ENGLISH["list"]]  # this channel's, sorted


async def test_similar_ids(cog: NtustCourseWatch) -> None:
    """Requirement: Members list their courses in the channel."""
    await cog.registrations.add("CE162A001", 5, 1)
    await cog.registrations.add("CE162A002", 5, 1)
    await cog.registrations.add("CE162A003", 5, 11)  # "11" contains "1": v3 listed it for 1
    fake = interaction(user=1, channel=5)

    await cog.list_courses(fake.as_interaction())

    assert replies(fake) == [ENGLISH["list"]]


async def test_nothing_registered(cog: NtustCourseWatch) -> None:
    """Requirement: Members list their courses in the channel."""
    await cog.registrations.add("CE162A001", 6, 1)
    fake = interaction(user=1, channel=5)

    await cog.list_courses(fake.as_interaction())

    assert replies(fake) == [ENGLISH["list-empty"]]  # v3's text with nothing after it


async def test_long_list(cog: NtustCourseWatch) -> None:
    """Requirement: Members list their courses in the channel."""
    codes = [f"CE162A{number:014d}" for number in range(100)]  # 20 characters each
    for code in codes:
        await cog.registrations.add(code, 5, 1)
    fake = interaction(user=1, channel=5)

    await cog.list_courses(fake.as_interaction())

    [reply] = replies(fake)
    assert len(reply.encode("utf-16-le")) // 2 <= 2000
    assert reply.startswith(ENGLISH["list-empty"] + ", ".join(codes[:80]))
    assert reply.endswith(", ...")


async def test_v3_document_listed_once(cog: NtustCourseWatch, store: Store) -> None:
    """Requirement: Registrations are kept as v3's document."""
    await store.put(NAMESPACE, KEY, {"CE162A001": {"5": ["1", "1"]}, "CE162A002": {"5": ["1"]}})
    fake = interaction(user=1, channel=5)

    await cog.list_courses(fake.as_interaction())

    assert replies(fake) == [ENGLISH["list"]]


@pytest.mark.parametrize(
    ("locale", "language"),
    [
        pytest.param(discord.Locale.taiwan_chinese, "zh-TW", id="zh-TW"),
        pytest.param(discord.Locale.american_english, "en-US", id="en-US"),
        pytest.param(discord.Locale.japanese, "en-US", id="ja: the default locale"),
    ],
)
async def test_replies_by_locale(
    cog: NtustCourseWatch, locale: discord.Locale, language: str
) -> None:
    """Requirement: Commands keep v3's names and answer in the member's locale."""
    texts = GOLDEN["replies"][language]
    calls = [
        (cog.add_course, ("CE162A002",), "registered"),
        (cog.add_course, ("CE162A001",), "registered"),
        (cog.list_courses, (), "list"),
        (cog.remove_course, ("CE162A001",), "unregistered"),
        (cog.remove_course, ("CE162A002",), "unregistered"),
        (cog.list_courses, (), "list-empty"),
        (cog.add_course, ("CE-1",), "invalid-code"),
    ]
    for method, arguments, key in calls:
        fake = interaction(locale=locale)
        await cast("Any", method)(fake.as_interaction(), *arguments)
        assert replies(fake) == [texts[key]], key
