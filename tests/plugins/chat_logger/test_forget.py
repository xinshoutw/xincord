"""Settings and stored messages are forgotten with the guild.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/Event.kt:127-130
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/ChatLogger.kt:241-244
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/DbManager.kt:22-31
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/DbManager.kt:125-127
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/JsonManager.kt:29-40
"""

import logging
from typing import TYPE_CHECKING

import pytest

from discord_fakes import FakeGuild
from plugin_fakes import dispatch
from xincord.core.bot import Bot
from xincord.plugins.chat_logger.cog import NAMESPACE
from xincord.plugins.chat_logger.messages import MessageLog
from xincord.plugins.listen_channels.store import ListenSettings

if TYPE_CHECKING:
    from conftest import Loader, Scene
    from xincord.core.storage import Store

# log_all true keeps the messages of a left guild until the retention, as v3 kept them; false
# deletes them, as v3 meant to (its deletion at the leave used the wrong key).
KEPT = [("log_all: true\n", [100, 200]), ("log_all: false\n", [200])]
LEFT = [("log_all: true\n", [100, 200]), ("log_all: false\n", [100])]


async def two_guilds(store: Store) -> None:
    """Guilds 10 and 20 have listen channel 5 and stored message 100 or 200."""
    messages = MessageLog(store)
    await messages.create()
    for guild_id, message_id in ((10, 100), (20, 200)):
        await ListenSettings(store, NAMESPACE).toggle(guild_id, 5)
        await messages.add(message_id, guild_id, 30, 7, "text")


async def stored(store: Store) -> list[int]:
    """The IDs of the stored messages."""
    rows = await store.run(
        lambda db: db.execute(
            "SELECT message_id FROM ChatLogger_messages ORDER BY message_id"
        ).fetchall()
    )
    return [row[0] for row in rows]


@pytest.mark.parametrize(("config", "kept"), KEPT)
async def test_the_bot_leaves(scene: Scene, kept: list[int]) -> None:
    """Requirement: Data is forgotten with the guild."""
    await two_guilds(scene.store)

    await dispatch(scene.bot, "guild_remove", scene.guild)  # guild 10

    assert await scene.store.keys(NAMESPACE) == ["20"]
    assert await stored(scene.store) == kept


@pytest.mark.parametrize(("config", "kept"), LEFT)
async def test_left_while_offline(
    scene: Scene, kept: list[int], caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Data is forgotten with the guild."""
    await two_guilds(scene.store)  # the bot knows guild 10 only: it left guild 20

    with caplog.at_level(logging.INFO):
        await dispatch(scene.bot, "ready")

    assert await scene.store.keys(NAMESPACE) == ["10"]
    assert await stored(scene.store) == kept
    assert "ChatLogger deleted the settings of guild 20, which the bot left" in caplog.text


async def test_messages_of_a_left_guild(scene: Scene, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Data is forgotten with the guild."""
    await two_guilds(scene.store)
    await scene.cog.messages.add(300, 30, 30, 7, "text")  # guild 30 had messages only

    with caplog.at_level(logging.INFO):
        await scene.cog.forget_left_guilds()

    assert await stored(scene.store) == [100, 200, 300]  # log_all true, the bundled default
    scene.cog.config = scene.cog.config.model_copy(update={"log_all": False})
    with caplog.at_level(logging.INFO):
        await scene.cog.forget_left_guilds()
    assert await stored(scene.store) == [100]
    assert "ChatLogger deleted the stored messages of guild 30, which the bot left" in caplog.text


async def test_loaded_into_a_ready_bot(
    store: Store, load: Loader, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: Data is forgotten with the guild."""
    await two_guilds(store)
    guilds = {10: FakeGuild(10)}

    def is_ready(_bot: Bot) -> bool:
        return True

    def get_guild(_bot: Bot, guild_id: int, /) -> FakeGuild | None:
        return guilds.get(guild_id)

    monkeypatch.setattr(Bot, "is_ready", is_ready)
    monkeypatch.setattr(Bot, "get_guild", get_guild)

    bot = await load("log_all: false\n")

    assert bot.loaded == ("ChatLogger",)
    assert await store.keys(NAMESPACE) == ["10"]
    assert await stored(store) == [100]
