"""Fixtures for the Ticket tests: the plugin loads through its real entry point.

The bot has its user, as after a login. ``scene`` runs the commands, presses the builder's
buttons, chooses in its selects and submits its modals as administrator 7 of guild 10, through
the plugin's route handler.
"""

import sys
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, cast

import discord
import pytest

from discord_fakes import BOT_USER, FakeChannel, FakeGuild, FakeInteraction, FakeMember, FakeMessage
from plugin_fakes import load_plugin
from xincord.core.bot import Bot
from xincord.plugins.ticket.cog import IDS, Session

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence
    from pathlib import Path

    from xincord.core.storage import Store
    from xincord.plugins.ticket.cog import Target, Ticket
    from xincord.plugins.ticket.model import Draft

PACKAGE = "xincord.plugins.ticket"
GUILD = 10
CHANNEL = 5  # the channel of the builder, where panels are posted
USER = 7  # the administrator who builds panels, unless a test says otherwise
MEMBER = 8  # a member without Administrator, who opens tickets
BUILDER = 43  # the ID of the builder message that shows the user's draft
COMPONENT = discord.InteractionType.component
MODAL = discord.InteractionType.modal_submit
COMMAND = discord.InteractionType.application_command
BUTTON = 2  # a button's component type
ROLE_SELECT = 6
CHANNEL_SELECT = 8


@pytest.fixture(autouse=True)
def plugin_modules() -> Iterator[None]:
    """The plugin's modules, the same before and after each test.

    discord.py drops a plugin's modules when its setup fails, and the next load imports new ones,
    whose dataclasses never equal those that the test modules imported.
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
    """The bot's user, which discord.py sets at the login, for v3's ``bot_*`` values."""
    monkeypatch.setattr(Bot, "user", property(lambda _bot: BOT_USER))


@pytest.fixture
async def bot(store: Store, tmp_path: Path) -> Bot:
    """A bot that loaded Ticket from `tmp_path / "plugins"` and never connects.

    The plugin's panels are in ``store``, the same store as the tests'.
    """
    return await load_plugin("Ticket", tmp_path / "plugins", store)


@pytest.fixture
def cog(bot: Bot) -> Ticket:
    """The loaded plugin's cog.

    No isinstance check: a failed load makes discord.py import the plugin's modules again, so the
    class may differ from the one imported when the tests were collected.
    """
    found = bot.get_cog("Ticket")
    assert found is not None
    return cast("Ticket", found)


@dataclass(frozen=True)
class Who:
    """Who acts: a member of guild 10, their client's locale, their permission and roles, and the
    message whose component they use."""

    user: int = USER
    locale: str = "en-US"
    admin: bool = True
    message_id: int = BUILDER
    name: str = "alice"
    roles: tuple[int, ...] = ()


ME = Who()  # administrator 7 with an en-US client, on the builder message


@dataclass
class Scene:
    """Guild 10 with Ticket loaded, where administrators build panels in ``channel``.

    The channel records its messages in its own ``sent`` list and finds the messages it holds.
    """

    bot: Bot
    store: Store
    guild: FakeGuild = field(default_factory=lambda: FakeGuild(GUILD))
    channel: FakeChannel = field(default_factory=lambda: FakeChannel(id=CHANNEL))

    @property
    def cog(self) -> Ticket:
        """The loaded plugin's cog."""
        found = self.bot.get_cog("Ticket")
        assert found is not None
        return cast("Ticket", found)

    @staticmethod
    def who(**changes: str | int | bool | tuple[int, ...]) -> Who:
        """Administrator 7 with an en-US client on the builder message, but for ``changes``.

        Test modules cannot import this module, so they build ``Who`` values here.
        """
        return replace(ME, **changes)

    def interaction(
        self, data: Mapping[str, object], kind: discord.InteractionType, who: Who = ME
    ) -> FakeInteraction:
        """An interaction of ``who`` in guild 10, from ``channel``."""
        roles = tuple(role for role in self.guild.roles if role.id in who.roles)
        interaction = FakeInteraction(
            data,
            type=kind,
            locale=discord.Locale(who.locale),
            user=FakeMember(self.guild, id=who.user, name=who.name, roles=roles),
            guild=self.guild,
            permissions=discord.Permissions(administrator=who.admin),
        )
        interaction.message = FakeMessage(sent=interaction.sent, id=who.message_id)
        interaction.channel = self.channel
        return interaction

    def keep(self, draft: Draft, who: Who = ME, target: Target | None = None) -> None:
        """Give ``who`` the draft ``draft``, shown in their builder message."""
        self.cog.drafts[who.user, GUILD] = Session(who.message_id, draft, target)

    def session(self, user: int = USER) -> Session:
        """The user's session."""
        return self.cog.drafts[user, GUILD]

    async def press(self, sub_action: str, who: Who = ME, **fields: str) -> FakeInteraction:
        """``who`` presses the builder button ``sub_action``."""
        custom_id = IDS.build({"action": "create", "sub_action": sub_action, **fields})
        interaction = self.interaction(
            {"component_type": BUTTON, "custom_id": custom_id}, COMPONENT, who
        )
        await self.cog.handle(interaction.as_interaction(), IDS.parse(custom_id))
        return interaction

    async def choose(
        self,
        sub_action: str,
        values: Sequence[str],
        who: Who = ME,
        component_type: int = CHANNEL_SELECT,
    ) -> FakeInteraction:
        """``who`` chooses ``values`` in the builder's select ``sub_action``."""
        custom_id = IDS.build({"action": "create", "sub_action": sub_action})
        data = {"component_type": component_type, "custom_id": custom_id, "values": list(values)}
        interaction = self.interaction(data, COMPONENT, who)
        await self.cog.handle(interaction.as_interaction(), IDS.parse(custom_id))
        return interaction

    async def submit(
        self, sub_action: str, values: Mapping[str, str], who: Who = ME
    ) -> FakeInteraction:
        """``who`` submits the builder's modal ``sub_action`` with ``values``, opened from their
        builder message.

        Each text input comes in a label, as Discord sends them.
        """
        custom_id = IDS.build({"action": "create", "sub_action": sub_action})
        return await self.submit_id(custom_id, values, who)

    async def submit_id(
        self, custom_id: str, values: Mapping[str, str], who: Who = ME
    ) -> FakeInteraction:
        """``who`` submits the modal ``custom_id`` with ``values``."""
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
    """Guild 10 with the plugin loaded."""
    return Scene(bot, store)
