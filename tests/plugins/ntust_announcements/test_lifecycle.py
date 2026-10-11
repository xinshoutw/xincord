"""The boards' loops: from READY until the plugin unloads, each board on its own.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementScheduler.kt:117-153
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementScheduler.kt:258-272
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/NtustManager.kt:66-72
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/NtustManager.kt:185-237
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/Event.kt:6-43
"""

import asyncio
import importlib
from typing import TYPE_CHECKING, cast

import discord
import pytest

from plugin_fakes import golden, load_plugin, until
from xincord.plugins.ntust_announcements.api import Api
from xincord.plugins.ntust_announcements.messages import HEADER
from xincord.plugins.ntust_announcements.web import open_web

if TYPE_CHECKING:
    from pathlib import Path

    from conftest import FakeWeb, Scene
    from plugin_fakes import Ready
    from xincord.core.storage import Store
    from xincord.plugins.ntust_announcements.cog import NtustAnnouncements

DORMITORY_URL = "https://student.ntust.edu.tw/p/403-1053-1436-1.php"
RECRUITMENT_URL = "https://lc.ntust.edu.tw/p/403-1070-1626-1.php"
FIRST_ARTICLE = golden("ntust_announcements")["entries"]["student-dormitory.html"][0]["url"]
BOARDS = "".join(
    f"""\
  - name: BOARD_{number}
    url: "{RECRUITMENT_URL}"
    layout: language-center
    channel-id: {100 + number}
"""
    for number in range(1, 9)
)
EIGHT_BOARDS = f"""\
fetch-interval: 3600
api-keys: ["key-1", "key-2", "key-3", "key-4"]
prompt: "{{{{page_url}}}} {{{{base_url}}}} {{{{now}}}} {{{{html}}}}"
boards:
{BOARDS}"""


async def turns(count: int = 20) -> None:
    """Let the other tasks run ``count`` times, without sleeping in real time."""
    for _ in range(count):
        await asyncio.sleep(0)


async def test_start_at_ready(scene: Scene) -> None:
    """Requirement: Boards are checked from READY until the plugin unloads."""
    assert scene.cog.tasks
    await scene.ready.waiters(1)

    # Nothing before READY: --no-online never gets there.
    assert scene.web.fetched == []
    assert scene.web.opened == 0

    scene.ready.set()
    await scene.clock.asleep(2)  # each board passed once and waits

    assert scene.clock.waits == [3600, 3600]
    assert scene.web.fetched[:2] == [DORMITORY_URL, RECRUITMENT_URL]
    assert len(scene.posts(101)) == 6
    assert len(scene.posts(102)) == 4
    assert scene.web.opened == 1


async def test_loaded_into_a_ready_bot(  # noqa: PLR0913, PLR0917 - pytest's fixtures
    store: Store,
    tmp_path: Path,
    ready: Ready,
    web: FakeWeb,
    config: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requirement: Boards are checked from READY until the plugin unloads."""
    web.pages = {DORMITORY_URL: "<p>none</p>", RECRUITMENT_URL: "<p>none</p>"}
    # The module that the load's import finds, as the cog's default web: discord.py executes the
    # plugin's package again but reuses its imported modules.
    module = importlib.import_module("xincord.plugins.ntust_announcements.cog")
    monkeypatch.setattr(module, "open_web", web.open)
    ready.set()  # as after /xincord reload NtustAnnouncements

    bot = await load_plugin("NtustAnnouncements", tmp_path / "plugins", store, config=config)
    cog = cast("NtustAnnouncements", bot.get_cog("NtustAnnouncements"))
    assert cog.tasks
    await until(lambda: len(web.fetched) >= 2)

    assert sorted(web.fetched) == sorted([DORMITORY_URL, RECRUITMENT_URL])


async def test_interval(scene: Scene) -> None:
    """Requirement: Boards are checked from READY until the plugin unloads."""
    assert scene.cog.tasks
    scene.ready.set()
    await scene.clock.asleep(2)

    await scene.clock.wake()
    await scene.clock.asleep(4)

    # fetch-interval seconds after each board's pass; the second pass finds nothing new.
    assert scene.clock.waits == [3600] * 4
    assert scene.web.fetched.count(DORMITORY_URL) == 2
    assert scene.web.fetched.count(RECRUITMENT_URL) == 2
    assert len(scene.posts(101)) == 6


async def test_boards_on_their_own(scene: Scene) -> None:
    """Requirement: Boards are checked from READY until the plugin unloads."""
    assert scene.cog.tasks
    scene.web.stuck.add(FIRST_ARTICLE)  # Gemini never answers the dormitory's first article
    scene.ready.set()

    await scene.clock.asleep(1)
    await scene.clock.wake()
    await scene.clock.asleep(2)

    # The Language Center's board passed twice while the dormitory's waited for Gemini.
    assert scene.clock.waits == [3600, 3600]
    assert scene.web.fetched.count(RECRUITMENT_URL) == 2
    assert len(scene.posts(102)) == 4
    assert scene.posts(101) == []


@pytest.mark.parametrize("config", [EIGHT_BOARDS])
async def test_fetches_at_a_time(scene: Scene) -> None:
    """Requirement: Boards are checked from READY until the plugin unloads."""
    assert scene.cog.tasks
    scene.web.hold = asyncio.Event()
    scene.ready.set()

    await until(lambda: len(scene.web.fetched) >= 5)
    await turns()
    assert len(scene.web.fetched) == 5  # v3's five at a time
    assert scene.web.under_way == 5

    scene.web.hold.set()
    await scene.clock.asleep(8)
    assert scene.clock.waits == [3600] * 8  # four keys convert the 32 articles without waiting
    assert scene.web.most == 5
    assert all(len(scene.posts(channel)) == 4 for channel in range(101, 109))


async def test_unload(scene: Scene) -> None:
    """Requirement: Boards are checked from READY until the plugin unloads."""
    [task] = scene.cog.tasks
    scene.ready.set()
    await scene.clock.asleep(2)
    fetched = len(scene.web.fetched)

    await scene.bot.remove_cog("NtustAnnouncements")  # what an unload or a reload does
    await scene.clock.wake()
    await turns()

    assert task.done()
    assert scene.web.closed == 1  # the session closed with the loops
    assert len(scene.web.fetched) == fetched


async def test_unload_before_ready(scene: Scene) -> None:
    """Requirement: Boards are checked from READY until the plugin unloads."""
    [task] = scene.cog.tasks
    await scene.ready.waiters(1)

    await scene.bot.remove_cog("NtustAnnouncements")  # as --no-online's unload

    assert task.done()
    assert scene.web.opened == 0


async def test_no_pings(scene: Scene) -> None:
    """Requirement: New announcements are posted in board order."""
    assert scene.cog.tasks
    scene.web.answer = "@everyone <@&1> Markdown"
    scene.ready.set()

    await scene.clock.asleep(2)

    assert scene.posts(101)[0] == f"{HEADER}\n@everyone <@&1> Markdown"
    for channel in scene.channels.values():
        for _, fields in channel.sent:
            mentions = fields["allowed_mentions"]
            assert isinstance(mentions, discord.AllowedMentions)
            assert mentions.to_dict() == discord.AllowedMentions.none().to_dict()


async def test_tests_stay_offline() -> None:
    """Requirement: Boards are checked from READY until the plugin unloads."""
    # The conftest's guard: a plugin that a test left with its real web reaches no NTUST page.
    async with open_web(Api()) as web:
        with pytest.raises(OSError, match="the tests do not reach the network"):
            await web.page(DORMITORY_URL)


async def test_reload(scene: Scene) -> None:
    """Requirement: Boards are checked from READY until the plugin unloads."""
    [old] = scene.cog.tasks
    await scene.ready.waiters(1)

    summary = await scene.bot.reload("NtustAnnouncements")  # the console's and /xincord's reload

    assert "NtustAnnouncements" in summary
    assert old.done()  # the old loops ended with the old cog
    cog = scene.cog  # the new version's
    [new] = cog.tasks
    cog.open_web = scene.web.open
    cog.sleep = scene.clock.sleep
    scene.ready.set()
    await scene.clock.asleep(2)

    assert not new.done()
    assert scene.web.opened == 1  # only the new cog's loops run
    assert len(scene.posts(101)) == 6
