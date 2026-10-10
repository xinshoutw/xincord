"""Fixtures for the ChatLogger tests: the plugin loads through its real entry point.

Discord's REST requests are recorded instead of sent, the bot has its user, as after a login, and
READY waits for the tests, as the plugin's retention loop waits for it. ``scene`` caches guild 10
in discord.py and feeds its gateway events through discord.py's own parsers. Every plugin that a
test loads is unloaded at its end, which closes its message files.
"""

import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import pytest

import payloads
from discord_fakes import BOT_USER, FakeChannel, FakeRest, embed_dict
from plugin_fakes import Ready, add_guild, gateway, load_plugin
from xincord.core.bot import Bot
from xincord.plugins.chat_logger.cog import NAMESPACE
from xincord.plugins.listen_channels.store import ListenSettings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterable, Iterator
    from pathlib import Path

    import discord

    from xincord.core.storage import Store
    from xincord.plugins.chat_logger.cog import ChatLogger

type Row = tuple[int, int, int, int, str, int]  # a stored message: v3's columns and the places

PACKAGE = "xincord.plugins.chat_logger"

GUILD = 10
MEMBER = 7  # the member who writes the messages, unless a test says otherwise
# Guild 10: category 20 holds text channel 30 (general) and its thread 41; category 21 holds text
# channel 32 (other); text channel 33 (loose) has no category.
CHANNELS = (
    payloads.channel(20, "chats", kind=4),
    payloads.channel(21, "more", kind=4),
    payloads.channel(30, "general", parent_id=20),
    payloads.channel(32, "other", parent_id=21),
    payloads.channel(33, "loose"),
)
THREADS = (payloads.thread(41, 30, GUILD),)


@pytest.fixture(autouse=True)
def rest(monkeypatch: pytest.MonkeyPatch) -> FakeRest:
    """Discord's REST requests, recorded instead of sent; each answers at once."""
    recorded = FakeRest()
    recorded.install(monkeypatch)
    return recorded


@pytest.fixture(autouse=True)
def logged_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bot's user, which discord.py sets at the login, for v3's ``bot_*`` values."""
    monkeypatch.setattr(Bot, "user", property(lambda _bot: BOT_USER))


@pytest.fixture(autouse=True)
async def ready(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[Ready]:
    """READY for the offline bots: the loops wait for it, and the ones left running are stopped."""
    readiness = Ready(monkeypatch)
    yield readiness
    await readiness.close()


@pytest.fixture(autouse=True)
def plugin_modules() -> Iterator[None]:
    """The plugin's modules, the same before and after each test.

    discord.py imports a plugin's modules again when it reloads the plugin or when a load fails
    (an invalid config), and the classes of the new modules differ from those that the test
    modules imported.
    """
    kept = {
        name: module
        for name, module in sys.modules.items()
        if name == PACKAGE or name.startswith(f"{PACKAGE}.")
    }
    yield
    sys.modules.update(kept)


class Loader:
    """Loads ChatLogger as startup does, offline, and keeps the bots to unload it at the end."""

    def __init__(self, store: Store, root: Path) -> None:
        self.store = store
        self.root = root
        self.bots: list[Bot] = []

    async def __call__(self, config: str | None = None) -> Bot:
        """A bot that loaded ChatLogger from ``root``, with the operator's ``config.yaml``."""
        bot = await load_plugin("ChatLogger", self.root, self.store, config=config)
        self.bots.append(bot)
        return bot


@pytest.fixture
async def load(store: Store, tmp_path: Path) -> AsyncGenerator[Loader]:
    """Load ChatLogger from `tmp_path / "plugins"`; its data directory is `tmp_path / "data"`.

    At the end, the plugin's cog leaves each bot, which closes the message files: a connection
    left open makes Python warn, and the warning fails a later test.
    """
    loader = Loader(store, tmp_path / "plugins")
    yield loader
    for bot in loader.bots:
        if bot.get_cog("ChatLogger") is not None:
            await bot.remove_cog("ChatLogger")


@pytest.fixture
def config() -> str | None:
    """The operator's ``config.yaml``, or None for the bundled one; tests parametrize it."""
    return None


@pytest.fixture
async def bot(load: Loader, config: str | None) -> Bot:
    """A bot that loaded ChatLogger from `tmp_path / "plugins"` and never connects.

    The plugin's settings are in ``store``, the same store as the tests', and its messages in
    `tmp_path / "data" / "ChatLogger"`.
    """
    return await load(config)


@pytest.fixture
def cog(bot: Bot) -> ChatLogger:
    """The loaded plugin's cog.

    No isinstance check: a load that fails, as with an invalid config, makes discord.py import the
    plugin's modules again, so the class differs from the one imported when the tests were
    collected.
    """
    found = bot.get_cog("ChatLogger")
    assert found is not None
    return cast("ChatLogger", found)


@dataclass
class Scene:
    """Guild 10 in discord.py's cache, with ChatLogger loaded, and what the plugin did there.

    Listen channels are reached as partial messageables: each one's messages are in ``channels``
    by ID, created at its first use. Put a channel there first to make it refuse posts.
    """

    bot: Bot
    store: Store
    rest: FakeRest
    guild: discord.Guild
    channels: dict[int, FakeChannel]
    directory: Path  # the plugin's data directory

    @property
    def cog(self) -> ChatLogger:
        """The loaded plugin's cog."""
        found = self.bot.get_cog("ChatLogger")
        assert found is not None
        return cast("ChatLogger", found)

    async def send(
        self, message_id: int, channel_id: int, content: str = "hello", author: int = MEMBER
    ) -> None:
        """User ``author``, a member of the guild, sends a message in ``channel_id``."""
        payload = payloads.message(
            message_id, channel_id, GUILD, payloads.user(author, f"user{author}"), content
        )
        await self.parse("MESSAGE_CREATE", payload)

    async def edit(
        self, message_id: int, channel_id: int, content: str, author: int = MEMBER
    ) -> None:
        """Discord sends the message's new state, as after its author edited it."""
        payload = payloads.message(
            message_id, channel_id, GUILD, payloads.user(author, f"user{author}"), content
        )
        await self.parse("MESSAGE_UPDATE", payload)

    async def delete(self, message_id: int, channel_id: int) -> None:
        """Somebody deletes a message of ``channel_id``."""
        payload: payloads.Payload = {
            "id": str(message_id),
            "channel_id": str(channel_id),
            "guild_id": str(GUILD),
        }
        await self.parse("MESSAGE_DELETE", payload)

    async def delete_all(self, message_ids: Iterable[int], channel_id: int) -> None:
        """Somebody deletes messages of ``channel_id`` at once, as a purge does."""
        ids = [str(message_id) for message_id in message_ids]
        payload: payloads.Payload = {
            "ids": ids,
            "channel_id": str(channel_id),
            "guild_id": str(GUILD),
        }
        await self.parse("MESSAGE_DELETE_BULK", payload)

    async def parse(self, event: str, payload: payloads.Payload) -> None:
        """Hand a gateway event to discord.py's parser and run the listeners it dispatched."""
        await gateway(self.bot, event, payload)

    async def listen(self, channel_id: int, allowed: list[int]) -> None:
        """Make ``channel_id`` a listen channel that allows the channels or categories given."""
        await ListenSettings(self.store, NAMESPACE).add_channels(
            GUILD, channel_id, "allow", allowed
        )

    async def rows(self) -> list[Row]:
        """The stored messages, by ID."""
        found = await self.store.run(
            lambda db: db.execute(
                "SELECT message_id, guild_id, channel_id, user_id, message, update_count"
                " FROM ChatLogger_messages ORDER BY message_id"
            ).fetchall()
        )
        return [tuple(row) for row in found]

    def files(self) -> dict[str, list[int]]:
        """The message IDs that each message file holds, by the file's name."""
        return {
            name: [row[0] for row in found] for name, found in file_rows(self.directory).items()
        }

    def posts(self, channel_id: int) -> list[dict[str, Any]]:
        """The embeds that listen channel ``channel_id`` got, one per post, as dicts."""
        channel = self.channels.get(channel_id)
        posts: list[dict[str, Any]] = []
        for _, fields in [] if channel is None else channel.sent:
            [embed] = cast("tuple[discord.Embed, ...]", fields["embeds"])
            posts.append(embed_dict(embed))
        return posts


@pytest.fixture
def scene(
    bot: Bot, store: Store, rest: FakeRest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Scene:
    """Guild 10 cached in the loaded bot, its posts recorded per listen channel."""
    created: dict[int, FakeChannel] = {}

    def partial(channel_id: int, *, guild_id: int | None = None) -> FakeChannel:
        assert guild_id == GUILD  # the listen channel's guild
        return created.setdefault(channel_id, FakeChannel(id=channel_id))

    monkeypatch.setattr(bot, "get_partial_messageable", partial)
    guild = add_guild(bot, payloads.guild(GUILD, channels=CHANNELS, threads=THREADS))
    return Scene(bot, store, rest, guild, created, tmp_path / "data" / "ChatLogger")


def file_rows(directory: Path) -> dict[str, list[Row]]:
    """Each message file's rows by the file's name, read through a connection of the test's own."""
    found: dict[str, list[Row]] = {}
    for path in sorted(directory.glob("messages-*.db")):
        with closing(sqlite3.connect(path)) as db:
            found[path.name] = [
                tuple(row)
                for row in db.execute(
                    "SELECT message_id, guild_id, channel_id, user_id, message, update_count"
                    " FROM messages ORDER BY message_id"
                )
            ]
    return found
