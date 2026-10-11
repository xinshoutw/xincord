"""Fixtures for the Giveaway tests: the plugin loads through its real entry point.

The bot has its user, as after a login, and READY waits for the tests, as the plugin's automatic
draw waits for it. ``scene`` runs the command, presses the builder's buttons and submits its modals
as administrator 7 of guild 10, through the plugin's route handler.
"""

import sys
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, cast

import discord
import pytest

from discord_fakes import (
    BOT_USER,
    FakeChannel,
    FakeGuild,
    FakeInteraction,
    FakeMember,
    FakeMessage,
)
from plugin_fakes import Ready, load_plugin
from xincord.core.bot import Bot
from xincord.plugins.giveaway.cog import IDS, Session
from xincord.plugins.giveaway.store import Giveaways

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator, Mapping
    from pathlib import Path

    from xincord.core.storage import Store
    from xincord.plugins.giveaway.cog import Giveaway
    from xincord.plugins.giveaway.model import Draft, Instance

PACKAGE = "xincord.plugins.giveaway"
NOW = 1772244000  # 2026-02-28 10:00 in Asia/Taipei, the tests' clock
GUILD = 10
CHANNEL = 5  # the channel of the builder, where giveaways are posted
USER = 7  # the administrator who builds the giveaway, unless a test says otherwise
MEMBER = 8  # a member without Administrator, who joins giveaways
BUILDER = 43  # the ID of the builder message that shows the user's draft
POST = 500  # the ID of a giveaway's post
COMPONENT = discord.InteractionType.component
MODAL = discord.InteractionType.modal_submit


@pytest.fixture(autouse=True)
def plugin_modules() -> Iterator[None]:
    """The plugin's modules, the same before and after each test.

    discord.py drops a plugin's modules when its setup fails (an invalid config), and the next load
    imports new ones, whose dataclasses never equal those that the test modules imported.
    """
    kept = {
        name: module
        for name, module in sys.modules.items()
        if name == PACKAGE or name.startswith(f"{PACKAGE}.")
    }
    yield
    sys.modules.update(kept)


@pytest.fixture(autouse=True)
def logged_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bot's user, which discord.py sets at the login, for the ``bot_*`` values."""
    monkeypatch.setattr(Bot, "user", property(lambda _bot: BOT_USER))


@pytest.fixture(autouse=True)
async def ready(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[Ready]:
    """READY for the offline bots: the loops wait for it, and the ones left running are stopped."""
    readiness = Ready(monkeypatch)
    yield readiness
    await readiness.close()


@pytest.fixture
def config() -> str | None:
    """The operator's ``config.yaml``, or None for the bundled one; tests parametrize it."""
    return None


@pytest.fixture
def files() -> dict[str, str]:
    """Operator files written under ``plugins/Giveaway/`` before the load; tests parametrize it."""
    return {}


@pytest.fixture
async def bot(store: Store, tmp_path: Path, config: str | None, files: dict[str, str]) -> Bot:
    """A bot that loaded Giveaway from `tmp_path / "plugins"` and never connects.

    The plugin's giveaways are in ``store``, the same store as the tests'.
    """
    root = tmp_path / "plugins"
    for name, text in files.items():
        path = root / "Giveaway" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return await load_plugin("Giveaway", root, store, config=config)


@pytest.fixture
def cog(bot: Bot) -> Giveaway:
    """The loaded plugin's cog.

    No isinstance check: test_config.py loads invalid files, after which discord.py imports the
    plugin's modules again, so the class differs from the one imported when the tests were
    collected.
    """
    found = bot.get_cog("Giveaway")
    assert found is not None
    return cast("Giveaway", found)


@dataclass(frozen=True)
class Who:
    """Who acts: a member of guild 10, their client's locale and permission, and the message."""

    user: int = USER
    locale: str = "en-US"
    admin: bool = True
    message_id: int = BUILDER  # the message whose component they use


ME = Who()  # administrator 7 with an en-US client, on the builder message
JOINER = Who(user=MEMBER, admin=False, message_id=POST)  # member 8 on the post


@dataclass
class Scene:
    """Guild 10 with Giveaway loaded, where users build giveaways in ``channel``.

    The channel records its messages in its own ``sent`` list; a test may replace it with one that
    refuses messages, or with an object that takes none.
    """

    bot: Bot
    store: Store
    channel: object = field(default_factory=lambda: FakeChannel(id=CHANNEL))

    @property
    def cog(self) -> Giveaway:
        """The loaded plugin's cog."""
        found = self.bot.get_cog("Giveaway")
        assert found is not None
        return cast("Giveaway", found)

    @staticmethod
    def who(**changes: str | int | bool) -> Who:
        """Administrator 7 with an en-US client on the builder message, but for ``changes``.

        Test modules cannot import this module, so they build ``Who`` values here.
        """
        return replace(ME, **changes)

    def interaction(
        self, data: Mapping[str, object], kind: discord.InteractionType, who: Who = ME
    ) -> FakeInteraction:
        """An interaction of ``who`` in guild 10."""
        guild = FakeGuild(GUILD)
        interaction = FakeInteraction(
            data,
            type=kind,
            locale=discord.Locale(who.locale),
            user=FakeMember(guild, id=who.user),
            guild=guild,
            permissions=discord.Permissions(administrator=who.admin),
        )
        interaction.message = FakeMessage(sent=interaction.sent, id=who.message_id)
        interaction.channel = self.channel
        return interaction

    def keep(self, draft: Draft, who: Who = ME) -> None:
        """Give ``who`` the draft ``draft``, shown in their builder message."""
        self.cog.drafts[who.user, GUILD] = Session(who.message_id, draft)

    def draft(self, user: int = USER) -> Draft:
        """The user's draft."""
        return self.cog.drafts[user, GUILD].draft

    async def press(self, sub_action: str, who: Who = ME) -> FakeInteraction:
        """``who`` presses the builder button ``sub_action``."""
        custom_id = IDS.build({"action": "create", "sub_action": sub_action})
        interaction = self.interaction(
            {"component_type": 2, "custom_id": custom_id}, COMPONENT, who
        )
        await self.cog.handle(interaction.as_interaction(), IDS.parse(custom_id))
        return interaction

    async def click(self, action: str, giveaway_id: str, who: Who = JOINER) -> FakeInteraction:
        """``who`` presses a post's button ``action`` of the giveaway ``giveaway_id``."""
        custom_id = IDS.build({"action": action, "giveaway_id": giveaway_id})
        data = {"component_type": 2, "custom_id": custom_id}
        interaction = self.interaction(data, COMPONENT, who)
        await self.cog.handle(interaction.as_interaction(), IDS.parse(custom_id))
        return interaction

    async def add(self, instance: Instance) -> None:
        """Store a giveaway, as a confirmation does."""
        await Giveaways(self.store).add(instance)

    async def stored(self, giveaway_id: str) -> Instance:
        """Guild 10's stored giveaway ``giveaway_id``."""
        found = await Giveaways(self.store).get(GUILD, giveaway_id)
        assert found is not None
        return found

    async def submit(
        self, sub_action: str, values: Mapping[str, str], who: Who = ME
    ) -> FakeInteraction:
        """``who`` submits the modal ``sub_action`` with ``values``, opened from their message.

        Each text input comes in a label, as Discord sends them.
        """
        custom_id = IDS.build({"action": "create", "sub_action": sub_action})
        components = [
            {
                "type": 18,
                "id": index * 2 + 1,
                "component": {"type": 4, "id": index * 2 + 2, "custom_id": key, "value": value},
            }
            for index, (key, value) in enumerate(values.items())
        ]
        data = {"custom_id": custom_id, "components": components}
        interaction = self.interaction(data, MODAL, who)
        await self.cog.handle(interaction.as_interaction(), IDS.parse(custom_id))
        return interaction


@pytest.fixture
def scene(bot: Bot, store: Store) -> Scene:
    """Guild 10 with the plugin loaded, at the tests' clock."""
    created = Scene(bot, store)
    created.cog.clock = lambda: NOW
    return created
