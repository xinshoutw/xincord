"""The listeners' loops start when the bot is ready and end with the plugin.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/Event.kt:10-54
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:55-135
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/BotLoader.kt:112-159
"""

import asyncio
import json
import logging
from typing import TYPE_CHECKING, cast

from discord.http import HTTPClient

from plugin_fakes import WAIT, load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from discord.http import Route

    from http_fakes import Monitor
    from plugin_fakes import Ready
    from xincord.core.storage import Store
    from xincord.plugins.uptime_heartbeat.cog import UptimeHeartbeat


async def load(tmp_path: Path, store: Store, *urls: str) -> UptimeHeartbeat:
    """Load the plugin with listeners that push ``urls`` every 60 seconds; return its cog.

    The cog is looked up without an isinstance check: test_config.py loads invalid files, after
    which discord.py imports the plugin's modules again.
    """
    entries = "".join(f"  - url: {json.dumps(url)}\n    interval: 60\n" for url in urls)
    bot = await load_plugin(
        "UptimeHeartbeat", tmp_path / "plugins", store, config=f"listeners:\n{entries}"
    )
    cog = bot.get_cog("UptimeHeartbeat")
    assert cog is not None
    return cast("UptimeHeartbeat", cog)


def plugin_problems(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The plugin's warnings and errors."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("xincord.plugins.uptime_heartbeat")
        and record.levelno >= logging.WARNING
    ]


async def test_pushes_start_when_the_bot_is_ready(
    tmp_path: Path, store: Store, monitor: Monitor, ready: Ready, discord_requests: list[Route]
) -> None:
    """Requirement: Pushing follows the bot's readiness and the plugin's lifetime."""
    cog = await load(tmp_path, store, monitor.url("/one?ping=%ping%"), monitor.url("/two"))
    tasks = cog.tasks

    await ready.waiters(len(tasks))  # both loops wait for READY
    assert len(tasks) == 2
    assert monitor.requests == []
    assert discord_requests == []

    ready.set()
    await monitor.received(2)

    pushed = {url.path: url.query for _, url in monitor.requests}
    assert pushed.keys() == {"/one", "/two"}
    assert pushed["/one"]["ping"].isdecimal()  # measured: not -1
    # Only the URL with %ping% asks Discord.
    assert [(route.method, route.path) for route in discord_requests] == [("GET", "/users/@me")]


async def test_loaded_into_a_ready_bot(
    tmp_path: Path, store: Store, monitor: Monitor, ready: Ready
) -> None:
    """Requirement: Pushing follows the bot's readiness and the plugin's lifetime."""
    ready.set()  # as after /xincord reload UptimeHeartbeat

    cog = await load(tmp_path, store, monitor.url("/one"))
    tasks = cog.tasks
    await monitor.received(1)

    assert len(tasks) == 1
    assert [url.path for _, url in monitor.requests] == ["/one"]


async def test_unloaded_during_a_push(
    tmp_path: Path,
    store: Store,
    monitor: Monitor,
    ready: Ready,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: Pushing follows the bot's readiness and the plugin's lifetime."""
    monitor.silent.add("/slow")
    ready.set()
    cog = await load(tmp_path, store, monitor.url("/slow"), monitor.url("/one"))
    tasks = cog.tasks
    await monitor.received(2)  # /slow waits for an answer, /one waits for its next push

    await cog.bot.remove_cog("UptimeHeartbeat")

    assert all(task.cancelled() for task in tasks)
    assert plugin_problems(caplog) == []  # v3 logged a spurious failure


async def test_unloaded_during_a_ping(
    tmp_path: Path,
    store: Store,
    ready: Ready,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: Pushing follows the bot's readiness and the plugin's lifetime."""
    asked = asyncio.Event()

    async def request(_http: HTTPClient, _route: Route, **_kwargs: object) -> object:
        asked.set()
        await asyncio.Event().wait()  # Discord does not answer
        return {}

    monkeypatch.setattr(HTTPClient, "request", request)
    ready.set()
    # Never contacted: the push waits for the ping.
    cog = await load(tmp_path, store, "http://127.0.0.1:9/api/push/x?ping=%ping%")
    tasks = cog.tasks
    async with asyncio.timeout(WAIT):
        await asked.wait()

    await cog.bot.remove_cog("UptimeHeartbeat")

    assert all(task.cancelled() for task in tasks)
    assert plugin_problems(caplog) == []


async def test_reload(tmp_path: Path, store: Store, monitor: Monitor, ready: Ready) -> None:
    """Requirement: Pushing follows the bot's readiness and the plugin's lifetime."""
    ready.set()
    old = await load(tmp_path, store, monitor.url("/old"))
    old_tasks = old.tasks
    await monitor.received(1)

    # A reload unloads the cog and runs setup again with the edited config.yaml.
    await old.bot.remove_cog("UptimeHeartbeat")
    new = await load(tmp_path, store, monitor.url("/new"))
    await monitor.received(2)

    assert all(task.done() for task in old_tasks)
    assert len(new.tasks) == 1
    assert [url.path for _, url in monitor.requests] == ["/old", "/new"]


async def test_independent_listeners(
    tmp_path: Path, store: Store, monitor: Monitor, ready: Ready
) -> None:
    """Requirement: Each listener pushes at once, then after a fixed delay."""
    monitor.silent.add("/silent")
    monitor.statuses["/gone"] = 404
    ready.set()

    cog = await load(
        tmp_path, store, monitor.url("/silent"), monitor.url("/gone"), monitor.url("/alive")
    )
    silent, gone, alive = cog.tasks
    await monitor.received(3)
    async with asyncio.timeout(WAIT):
        await gone  # the 404 ends this loop only

    assert {url.path for _, url in monitor.requests} == {"/silent", "/gone", "/alive"}
    assert not silent.done()
    assert not alive.done()  # waiting for its next push
