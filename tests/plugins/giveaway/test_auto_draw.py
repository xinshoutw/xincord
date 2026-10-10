"""The automatic draw: due giveaways are drawn five seconds after READY, then at each interval.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:93-185
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:430-469
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Event.kt:27-67
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Event.kt:114-117
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/resources/lang/en-US/message/auto-draw-result.yaml:1
"""

import asyncio
import logging
import random
import sqlite3
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, cast

import pytest

from discord_fakes import FakeChannel, FakeGuild, embed_dict, forbidden, not_found
from plugin_fakes import WAIT, golden
from xincord.plugins.giveaway.model import Draft, Instance, Prize, draw_winners
from xincord.plugins.giveaway.store import Giveaways

if TYPE_CHECKING:
    import discord

    from conftest import Scene
    from plugin_fakes import Ready
    from xincord.core.templates import Message

GOLDEN = golden("giveaway")
NOW = 1772244000  # the tests' clock
DUE = Instance(
    id="3f2a9c1b7e4d4a60",
    guild_id=10,
    channel_id=5,
    message_id=500,
    creator_id=7,
    config=Draft(title="Nitro", end_at=NOW - 3600, prizes=(Prize("Nitro", 1),)),
    locale_tag="en-US",
    participant_ids=(111,),
)


class Ticks:
    """The loop's sleep and clock: each sleep is recorded, waits for :meth:`wake`, then moves on.

    The clock moves forward by the delay that ended, as time would have.
    """

    def __init__(self, now: float) -> None:
        self.now = now
        self.delays: list[float] = []
        self._asleep = asyncio.Event()
        self._wake = asyncio.Event()

    def time(self) -> float:
        """Now."""
        return self.now

    async def sleep(self, delay: float) -> None:
        """Record the delay, wait for :meth:`wake`, then move the clock by it."""
        self.delays.append(delay)
        self._asleep.set()
        await self._wake.wait()
        self._wake.clear()
        self.now += delay

    async def asleep(self) -> None:
        """Wait until the loop sleeps again."""
        async with asyncio.timeout(WAIT):
            await self._asleep.wait()
        self._asleep.clear()

    async def wake(self) -> None:
        """End the loop's sleep and wait until it sleeps again, a pass later."""
        self._wake.set()
        await self.asleep()


@dataclass
class Draws:
    """The scene with the automatic draw's clock, its guilds and their channels."""

    scene: Scene
    ticks: Ticks
    guilds: dict[int, FakeGuild]
    channels: dict[int, FakeChannel] = field(default_factory=dict[int, FakeChannel])

    def sent(self, channel_id: int = 5) -> list[tuple[str, dict[str, object]]]:
        """What the channel got: post edits and announcements."""
        channel = self.channels.get(channel_id)
        return [] if channel is None else list(channel.sent)

    async def start(self, ready: Ready) -> asyncio.Task[None]:
        """READY: the loop sleeps its first five seconds; return it."""
        [loop] = self.scene.cog.tasks
        ready.set()
        await self.ticks.asleep()
        return loop


@pytest.fixture
def draws(scene: Scene, monkeypatch: pytest.MonkeyPatch) -> Draws:
    """Guild 10 is available; its channels are partial messageables, recorded by ID."""
    ticks = Ticks(NOW)
    scene.cog.sleep = ticks.sleep
    scene.cog.clock = ticks.time
    guilds = {10: FakeGuild(10)}
    found = Draws(scene, ticks, guilds)

    def partial(channel_id: int, *, guild_id: int | None = None) -> FakeChannel:
        assert guild_id is not None
        return found.channels.setdefault(channel_id, FakeChannel(id=channel_id))

    monkeypatch.setattr(scene.bot, "get_partial_messageable", partial)
    monkeypatch.setattr(scene.bot, "get_guild", guilds.get)
    return found


def seeded(seed: int) -> random.Random:
    """A generator whose draws the test can repeat; the plugin draws with SystemRandom."""
    return random.Random(seed)  # noqa: S311 - reproducible draws, not secrets


def announced(draws: Draws, channel_id: int = 5) -> list[object]:
    """The announcements that the channel got."""
    return [
        fields["content"] for method, fields in draws.sent(channel_id) if method == "channel.send"
    ]


async def test_first_pass(draws: Draws, ready: Ready) -> None:
    """Requirement: Due giveaways are drawn automatically."""
    scene = draws.scene
    await scene.add(DUE)  # its end time passed while the bot was offline
    scene.cog.random = seeded(3)

    [loop] = scene.cog.tasks
    await ready.waiters(1)  # nothing is drawn before READY, as under --no-online
    assert await draws.start(ready) is loop
    assert draws.ticks.delays == [5]  # v3's initial delay
    assert not (await scene.stored(DUE.id)).ended
    await draws.ticks.wake()

    stored = await scene.stored(DUE.id)
    winners = draw_winners(DUE.config.prizes, DUE.config.policy, DUE.participant_ids, seeded(3))
    assert stored == replace(DUE, ended=True, ended_at=NOW + 5, winner_results=winners)
    (edited, post), (sent, _) = draws.sent()
    assert (edited, sent) == ("message.edit", "channel.send")
    [embed] = cast("tuple[discord.Embed, ...]", post["embeds"])
    assert embed_dict(embed)["fields"][4]["value"] == "Nitro: <@111>"
    assert announced(draws) == [GOLDEN["announcement"]["en-US"].format(body="Nitro: <@111>")]
    assert draws.ticks.delays == [5, 60]
    assert not loop.done()


async def test_later_passes(draws: Draws) -> None:
    """Requirement: Due giveaways are drawn automatically."""
    scene = draws.scene
    await scene.add(replace(DUE, config=replace(DUE.config, end_at=NOW + 30)))

    await scene.cog.draw_due()
    assert not (await scene.stored(DUE.id)).ended
    draws.ticks.now = NOW + 30  # the end time has come
    await scene.cog.draw_due()
    draws.ticks.now = NOW + 90
    await scene.cog.draw_due()

    stored = await scene.stored(DUE.id)
    assert stored.ended
    assert stored.ended_at == NOW + 30
    assert len(announced(draws)) == 1  # drawn once


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_language(draws: Draws, locale: str) -> None:
    """Requirement: Due giveaways are drawn automatically."""
    scene = draws.scene
    await scene.add(replace(DUE, locale_tag=locale))

    await scene.cog.draw_due()

    assert announced(draws) == [GOLDEN["announcement"][locale].format(body="Nitro: <@111>")]


async def test_skipped_guilds(draws: Draws) -> None:
    """Requirement: Due giveaways are drawn automatically."""
    scene = draws.scene
    left = replace(DUE, id="0000000000000011", guild_id=11)
    unavailable = replace(DUE, id="0000000000000012", guild_id=12)
    await scene.add(left)
    await scene.add(unavailable)
    draws.guilds[12] = FakeGuild(12, unavailable=True)

    await scene.cog.draw_due()
    assert announced(draws) == []
    draws.guilds[11] = FakeGuild(11)  # the bot is back in guild 11
    draws.guilds[12] = FakeGuild(12)  # and guild 12 is back
    await scene.cog.draw_due()

    giveaways = scene.cog.giveaways
    assert all(
        [(await giveaways.get(guild, id_)) for guild, id_ in ((11, left.id), (12, unavailable.id))]
    )
    assert len(announced(draws)) == 2


async def test_post_gone(draws: Draws, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Due giveaways are drawn automatically."""
    scene = draws.scene
    draws.channels[5] = FakeChannel(id=5, error=forbidden(), message_error=not_found())
    other = replace(DUE, id="0000000000000006", channel_id=6, message_id=600)
    await scene.add(DUE)
    await scene.add(other)

    with caplog.at_level(logging.WARNING):
        await scene.cog.draw_due()

    assert (await scene.stored(DUE.id)).ended  # stored before anything was posted
    assert f"Giveaway cannot update the post of giveaway {DUE.id}" in caplog.text
    assert f"Giveaway cannot announce the winners of giveaway {DUE.id}" in caplog.text
    assert len(announced(draws, 6)) == 1  # the other giveaway is still handled


@pytest.mark.xfail(strict=True, reason="Due giveaways are drawn automatically")
async def test_broken_data(draws: Draws, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Due giveaways are drawn automatically."""
    scene = draws.scene
    draws.guilds[11] = FakeGuild(11)
    await scene.store.put("Giveaway", "11", ["not", "a", "document"])
    await scene.store.put("Giveaway", "x", {})  # not a guild ID: never a guild
    await scene.add(DUE)
    entry: dict[str, Any] = {"id": "broken"}
    document = await scene.store.get("Giveaway", "10")
    assert isinstance(document, dict)
    await scene.store.put("Giveaway", "10", {**document, "broken": entry})

    with caplog.at_level(logging.WARNING):
        await scene.cog.draw_due()
        await scene.cog.draw_due()

    assert (await scene.stored(DUE.id)).ended
    # Each broken document or entry is a warning once, not a traceback at every pass.
    assert caplog.text.count("Giveaway skips guild 11 in the automatic draw") == 1
    assert caplog.text.count("Giveaway skips guild 10, giveaway broken in the automatic draw") == 1
    assert "Traceback" not in caplog.text


async def test_store_fails_for_a_guild(
    draws: Draws, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Due giveaways are drawn automatically."""
    scene = draws.scene
    draws.guilds[11] = FakeGuild(11)
    await scene.add(replace(DUE, id="0000000000000011", guild_id=11))
    await scene.add(DUE)
    draw_due = Giveaways.draw_due

    async def failing(
        giveaways: Giveaways, guild_id: int, now: int, rng: random.Random
    ) -> list[Instance]:
        if guild_id == 11:
            message = "database is locked"
            raise sqlite3.OperationalError(message)
        return await draw_due(giveaways, guild_id, now, rng)

    monkeypatch.setattr(Giveaways, "draw_due", failing)
    await scene.cog.draw_due()

    assert "Giveaway cannot draw the due giveaways of guild 11" in caplog.text
    assert (await scene.stored(DUE.id)).ended  # the other guild is handled


async def test_failed_pass(
    draws: Draws, ready: Ready, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Due giveaways are drawn automatically."""
    calls: list[str] = []

    async def keys(namespace: str) -> list[str]:
        calls.append(namespace)
        message = "database is locked"
        raise sqlite3.OperationalError(message)

    monkeypatch.setattr(draws.scene.store, "keys", keys)
    loop = await draws.start(ready)
    await draws.ticks.wake()
    await draws.ticks.wake()

    assert calls == ["Giveaway", "Giveaway"]  # the loop goes on
    assert "Giveaway's automatic draw failed" in caplog.text
    assert not loop.done()


@pytest.mark.parametrize("config", ["autoDrawIntervalSeconds: 1\n"])
async def test_clamped_period(draws: Draws, ready: Ready) -> None:
    """Requirement: Due giveaways are drawn automatically."""
    await draws.start(ready)
    await draws.ticks.wake()

    assert draws.ticks.delays == [5, 5]


async def test_unload(draws: Draws, ready: Ready) -> None:
    """Requirement: Due giveaways are drawn automatically."""
    loop = await draws.start(ready)

    await draws.scene.bot.remove_cog("Giveaway")  # runs cog_unload, as an unload or a reload does

    assert loop.cancelled()


async def test_failed_announcement(
    draws: Draws, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Due giveaways are drawn automatically."""
    scene = draws.scene
    other = replace(DUE, id="0000000000000006", channel_id=6, message_id=600)
    await scene.add(DUE)
    await scene.add(other)
    render = scene.cog.render_post

    def failing(instance: Instance) -> Message:
        if instance.id == DUE.id:
            message = "a broken operator template"
            raise RuntimeError(message)
        return render(instance)

    monkeypatch.setattr(scene.cog, "render_post", failing)
    with caplog.at_level(logging.ERROR):
        await scene.cog.draw_due()

    assert len(announced(draws, 6)) == 1  # the pass goes on after the failure
    assert f"Giveaway cannot post the draw of giveaway {DUE.id}" in caplog.text
