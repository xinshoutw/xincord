"""Voice channel status changes, posted with the member that the audit log names.

discord.py 2.7.1 does not parse ``VOICE_CHANNEL_STATUS_UPDATE``; the plugin relays it.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/Event.kt:101-104
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:117-141
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:163-184
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:231-276
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/resources/lang/en-US/message/on-status-new.yaml:1-21
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any, cast

import discord
import pytest
from discord.utils import time_snowflake, utcnow

from discord_fakes import FakeGuild, FakeMember, FakeVoiceChannel, embed_dict, forbidden
from plugin_fakes import dispatch, gateway, golden, until
from xincord.plugins.listen_channels.store import ListenSettings
from xincord.plugins.voice_logger.cog import NAMESPACE
from xincord.plugins.voice_logger.status import CLEARED, SET

if TYPE_CHECKING:
    from discord_fakes import FakeChannel, FakeRest
    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.voice_logger.cog import VoiceLogger

GOLDEN = golden("voice_logger")
LOCALES = {"en-US": discord.Locale.american_english, "zh-TW": discord.Locale.taiwan_chinese}
STATUS = "VOICE_CHANNEL_STATUS_UPDATE"
AUDIT = "GET /guilds/10/audit-logs"


def settings(store: Store) -> ListenSettings:
    """VoiceLogger's listen channel settings in ``store``."""
    return ListenSettings(store, NAMESPACE)


@dataclass
class Scene:
    """The loaded plugin with guild 10 cached, its REST requests and its listen channels.

    Guild 10 has member 7, the voice channels Room A (30) and Room B (33) of category 20, and the
    stage channel Stage (31).
    """

    bot: Bot
    store: Store
    rest: FakeRest
    channels: dict[int, FakeChannel]
    guild: FakeGuild

    async def listen(self, channel_id: int, allowed: list[int]) -> None:
        """Make ``channel_id`` a listen channel that allows the channels or categories given."""
        await settings(self.store).add_channels(10, channel_id, "allow", allowed)

    def answer(self, *entries: list[dict[str, object]]) -> None:
        """Answer the next reads of the audit log with these entries, one list per read."""
        self.rest.answers[AUDIT] = [{"audit_log_entries": found, "users": []} for found in entries]

    async def update(self, status: str | None, *, channel_id: int = 30, guild_id: int = 10) -> None:
        """Discord changes the status of ``channel_id``: run the listener of the relayed event."""
        await dispatch(
            self.bot, "gateway_voice_channel_status_update", update(status, channel_id, guild_id)
        )

    def posts(self, channel_id: int) -> list[dict[str, Any]]:
        """The embeds that the listen channel ``channel_id`` received, one per message."""
        found: list[dict[str, Any]] = []
        for method, fields in self.channels[channel_id].sent:
            assert method == "channel.send"
            [embed] = cast("tuple[discord.Embed, ...]", fields["embeds"])
            found.append(embed_dict(embed))
        return found


@pytest.fixture
def scene(
    bot: Bot,
    store: Store,
    rest: FakeRest,
    channels: dict[int, FakeChannel],
    monkeypatch: pytest.MonkeyPatch,
) -> Scene:
    """The plugin's world for status changes, with guild 10 in the bot's cache."""
    guild = FakeGuild(10, "guild")
    guild.channels = [
        FakeVoiceChannel(id=30, name="Room A", guild=guild, category_id=20),
        FakeVoiceChannel(id=31, name="Stage", type=discord.ChannelType.stage_voice, guild=guild),
        FakeVoiceChannel(id=33, name="Room B", guild=guild, category_id=20),
    ]
    guild.members = [FakeMember(guild, id=7)]
    monkeypatch.setattr(bot, "get_guild", {10: guild}.get)
    return Scene(bot, store, rest, channels, guild)


@pytest.fixture
def sleeps(cog: VoiceLogger, monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """The plugin's waits before reading the audit log again, recorded instead of waited."""
    waited: list[float] = []

    async def sleep(seconds: float) -> None:
        waited.append(seconds)

    monkeypatch.setattr(cog, "sleep", sleep, raising=False)
    return waited


def update(status: str | None, channel_id: int = 30, guild_id: int = 10) -> dict[str, object]:
    """Discord's payload of a status change of voice channel ``channel_id``."""
    return {"id": str(channel_id), "guild_id": str(guild_id), "status": status}


def entry(
    user_id: int, *, kind: int = SET, status: str | None = None, channel_id: int = 30
) -> dict[str, object]:
    """An audit log entry that ``user_id`` made a second ago for ``channel_id``."""
    options: dict[str, object] = {"channel_id": str(channel_id)}
    if status is not None:
        options["status"] = status
    return {
        "id": str(time_snowflake(utcnow() - timedelta(seconds=1))),
        "action_type": kind,
        "user_id": str(user_id),
        "target_id": None,
        "options": options,
    }


def without_member(embed: dict[str, Any]) -> dict[str, Any]:
    """``embed`` as it shows when no member is known: ``-`` and no thumbnail."""
    fields = [dict(field) for field in embed["fields"]]
    fields[0]["value"] = "-"
    return {key: value for key, value in embed.items() if key != "thumbnail"} | {"fields": fields}


def read(type_: int) -> tuple[str, dict[str, object]]:
    """The request that reads the guild's audit log of type ``type_``."""
    return (AUDIT, {"json": None, "params": {"action_type": type_, "limit": 10}})


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_new_status(scene: Scene, locale: str) -> None:
    """Requirement: Voice channel status changes are logged."""
    scene.guild.preferred_locale = LOCALES[locale]
    await scene.listen(5, [30])
    scene.answer([entry(7, status="Gaming")])

    await scene.update("Gaming")

    assert scene.posts(5) == [GOLDEN["status"][locale]["new"]]
    assert scene.rest.sent == [read(SET)]


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_changed_and_cleared_status(scene: Scene, locale: str) -> None:
    """Requirement: Voice channel status changes are logged."""
    scene.guild.preferred_locale = LOCALES[locale]
    await scene.listen(5, [20])  # the category
    scene.answer([entry(7, status="Gaming")], [entry(7, status="Chill")], [entry(7, kind=CLEARED)])

    await scene.update("Gaming")
    await scene.update("Chill")
    await scene.update(None)  # Discord's null for a cleared status

    expected = GOLDEN["status"][locale]
    assert scene.posts(5) == [expected["new"], expected["update"], expected["delete"]]
    assert scene.rest.sent == [read(SET), read(SET), read(CLEARED)]  # v3 read type 192 each time


async def test_nothing_to_log(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Voice channel status changes are logged."""
    await settings(scene.store).toggle(10, 5)  # the block mode, nothing blocked: every channel
    scene.answer([entry(7, status="Gaming")])
    await scene.update("Gaming")
    scene.rest.sent.clear()
    scene.channels[5].sent.clear()

    await scene.update("Gaming")  # unchanged
    await scene.update("", channel_id=33)  # unknown, so empty: unchanged
    await scene.update("Gaming", channel_id=31)  # a stage channel
    await scene.update("Gaming", channel_id=99)  # not cached
    await scene.update("Gaming", guild_id=11)  # a guild that is not cached
    await dispatch(scene.bot, "gateway_voice_channel_status_update", {"id": "30"})  # no guild

    assert scene.rest.sent == []
    assert scene.channels[5].sent == []
    assert "VoiceLogger ignored a malformed voice channel status update" in caplog.text


async def test_relayed(scene: Scene) -> None:
    """Requirement: Voice channel status changes are logged."""
    # Through discord.py's parser table, as its gateway hands the event over.
    await scene.listen(5, [30])
    scene.answer([entry(7, status="Gaming")])

    await gateway(scene.bot, STATUS, update("Gaming"))

    assert scene.posts(5) == [GOLDEN["status"]["en-US"]["new"]]


async def test_late_entry(scene: Scene, sleeps: list[float]) -> None:
    """Requirement: Status changes name their member from the audit log."""
    await scene.listen(5, [30])
    scene.answer([], [entry(7, status="Gaming")])

    await scene.update("Gaming")

    assert scene.posts(5) == [GOLDEN["status"]["en-US"]["new"]]
    assert (scene.rest.sent, sleeps) == ([read(SET), read(SET)], [2.0])


async def test_no_entry(scene: Scene, sleeps: list[float]) -> None:
    """Requirement: Status changes name their member from the audit log."""
    # As for a status that Discord clears by itself: v3 named whoever last set any status.
    await scene.listen(5, [30])
    scene.answer([], [entry(7, status="Gaming", channel_id=33)])

    await scene.update("Gaming")

    assert scene.posts(5) == [without_member(GOLDEN["status"]["en-US"]["new"])]
    assert sleeps == [2.0]


async def test_audit_log_refused(
    scene: Scene, sleeps: list[float], caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Status changes name their member from the audit log."""
    # v3 posted nothing without View Audit Log.
    await scene.listen(5, [30])
    scene.rest.errors[AUDIT] = forbidden()

    await scene.update("Gaming")

    assert scene.posts(5) == [without_member(GOLDEN["status"]["en-US"]["new"])]
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert [record.getMessage() for record in warnings] == [
        (
            "VoiceLogger cannot read the audit log of guild (10): "
            "403 Forbidden (error code: 0): Missing Permissions"
        )
    ]
    assert sleeps == []


async def test_member_gone(scene: Scene) -> None:
    """Requirement: Status changes name their member from the audit log."""
    await scene.listen(5, [30])
    scene.answer([entry(8, status="Gaming")])  # member 8 left the guild

    await scene.update("Gaming")

    assert scene.posts(5) == [without_member(GOLDEN["status"]["en-US"]["new"])]


async def test_not_detected(scene: Scene) -> None:
    """Requirement: Status changes name their member from the audit log."""
    # v3 read the audit log and fetched the member before it looked for listen channels.
    await scene.listen(5, [99])

    await scene.update("Gaming")

    assert scene.rest.sent == []
    assert scene.channels == {}


async def test_typed_text_stays(scene: Scene) -> None:
    """Requirement: Voice channel status changes are logged."""
    # v3 expanded placeholders in statuses, and a status naming its own key made the log throw.
    typed = "%vl_status_after% %user_mention%"
    await scene.listen(5, [30])
    scene.answer([entry(7, status=typed)])

    await scene.update(typed)

    [posted] = scene.posts(5)
    assert posted["fields"][3]["value"] == typed


async def test_a_change_waits_for_its_entry(
    scene: Scene, cog: VoiceLogger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: Status changes are posted in order from the current session."""
    # A status that Discord clears by itself has no entry at first, and a member sets a new one.
    await scene.listen(5, [30])
    scene.answer(
        [entry(7, status="Gaming")], [], [entry(7, kind=CLEARED)], [entry(7, status="Again")]
    )
    await scene.update("Gaming")
    gate, waits = asyncio.Event(), list[float]()

    async def sleep(seconds: float) -> None:
        waits.append(seconds)
        if len(waits) == 1:  # the clear waits until the test lets it read again
            await gate.wait()

    monkeypatch.setattr(cog, "sleep", sleep)
    cleared = asyncio.create_task(scene.update(None))
    await until(lambda: bool(waits))
    again = asyncio.create_task(scene.update("Again"))
    # Room for the new status to be posted first, which must not happen; a store read takes
    # milliseconds.
    await asyncio.wait({again}, timeout=0.2)
    gate.set()
    await asyncio.gather(cleared, again)

    expected = GOLDEN["status"]["en-US"]
    new, delete = expected["new"]["title"], expected["delete"]["title"]
    assert [post["title"] for post in scene.posts(5)] == [new, delete, new]


async def test_a_new_session_or_an_outage(scene: Scene) -> None:
    """Requirement: Status changes are posted in order from the current session."""
    # JDA rebuilt its cache from the new session's channels, which hold no status.
    await scene.listen(5, [30])
    scene.answer(*[[entry(7, status="Gaming")]] * 3)

    await scene.update("Gaming")
    await dispatch(scene.bot, "ready")
    await scene.update("Gaming")
    await dispatch(scene.bot, "guild_unavailable", scene.guild.as_guild())
    await scene.update("Gaming")

    assert scene.posts(5) == [GOLDEN["status"]["en-US"]["new"]] * 3


async def test_the_bot_leaves(scene: Scene, cog: VoiceLogger) -> None:
    """Requirement: Status changes are posted in order from the current session."""
    await scene.listen(5, [30])
    scene.answer([entry(7, status="Gaming")])
    await scene.update("Gaming")

    await dispatch(scene.bot, "guild_remove", scene.guild.as_guild())

    assert cog.statuses == {}
