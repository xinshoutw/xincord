"""Plugin discovery, loading and reloading.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/PluginLoader.kt:39-245
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/plugin/PluginEvent.kt:14-74
"""

import logging
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import discord
import pytest

from xincord.core.bot import Bot
from xincord.core.plugins import GROUP, PluginError, PluginInfo, discover, required_intents

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from aiohttp import ClientResponse
    from discord.types.components import ActionRow as ActionRowPayload
    from discord.types.components import ContainerComponent as ContainerPayload

    from plugin_fakes import FakePlugins
    from xincord.core.storage import Store

RECORD = """
from .. import calls


async def setup(bot):
    calls.append(bot.plugin_context(__name__).info.name)
"""
CONFIGURED = """
from xincord.core.config import Model

from .. import calls


class Config(Model):
    greeting: str


async def setup(bot):
    context = bot.plugin_context(__name__)
    config = context.config(Config)
    lang = context.lang("en-US")
    calls.append((config.greeting, lang.locales, context.directory, context.store))
"""
BUNDLE = {"config.yaml": "greeting: Hello\n", "lang/en-US/register.yaml": "greet:\n  name: greet\n"}


def test_enabled_plugins_are_discovered(fake_plugins: FakePlugins) -> None:
    """Requirement: Plugins are discovered through entry points."""
    module = fake_plugins.add(
        "Alpha",
        """
        import discord

        SOFT_DEPENDS = ("Gamma",)
        INTENTS = discord.Intents(members=True)
        """,
    )
    fake_plugins.add("Beta")

    infos = discover(["Alpha"], fake_plugins.entry_points)

    assert infos == [
        PluginInfo("Alpha", module, (), ("Gamma",), discord.Intents(members=True)),
    ]


def test_installed_group_is_the_default(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Plugins are discovered through entry points."""
    with caplog.at_level(logging.ERROR):
        assert discover(["NotInstalled"]) == []

    assert "NotInstalled" in caplog.text


@pytest.mark.parametrize(
    "source",
    [
        "raise RuntimeError('boom')\n",
        "DEPENDS = 'Alpha'\n",
        "SOFT_DEPENDS = ('Alpha', 1)\n",
        "INTENTS = 3\n",
    ],
)
def test_broken_plugins_are_left_out(
    fake_plugins: FakePlugins, caplog: pytest.LogCaptureFixture, source: str
) -> None:
    """Requirement: Plugins are discovered through entry points."""
    fake_plugins.add("Alpha")
    fake_plugins.add("Broken", source)
    evil = EntryPoint(name="../Evil", value=f"{fake_plugins.package}.alpha", group=GROUP)

    with caplog.at_level(logging.ERROR):
        infos = discover(
            ["Missing", "Alpha", "Broken", "../Evil"], [*fake_plugins.entry_points, evil]
        )

    assert [info.name for info in infos] == ["Alpha"]
    for name in ("Missing", "Broken", "../Evil"):
        assert name in caplog.text


def test_dependencies_first(fake_plugins: FakePlugins) -> None:
    """Requirement: Plugins load in dependency order."""
    fake_plugins.add("Alpha")
    fake_plugins.add("Beta", "SOFT_DEPENDS = ('Alpha',)\n")
    fake_plugins.add("Gamma", "DEPENDS = ('Beta',)\n")

    infos = discover(["Gamma", "Beta", "Alpha"], fake_plugins.entry_points)

    assert [info.name for info in infos] == ["Alpha", "Beta", "Gamma"]


def test_missing_dependencies_and_cycles(
    fake_plugins: FakePlugins, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Plugins load in dependency order."""
    fake_plugins.add("Alpha")
    fake_plugins.add("Delta", "DEPENDS = ('Omega',)\n")
    fake_plugins.add("Epsilon", "DEPENDS = ('Delta',)\n")
    fake_plugins.add("Zeta", "DEPENDS = ('Eta',)\n")
    fake_plugins.add("Eta", "DEPENDS = ('Zeta',)\n")
    fake_plugins.add("Theta", "SOFT_DEPENDS = ('Delta',)\n")

    with caplog.at_level(logging.ERROR):
        infos = discover(
            ["Alpha", "Delta", "Epsilon", "Zeta", "Eta", "Theta"], fake_plugins.entry_points
        )

    assert [info.name for info in infos] == ["Alpha", "Theta"]
    for name in ("Delta", "Epsilon", "Zeta", "Eta"):
        assert name in caplog.text


def test_plugin_intents_are_added(fake_plugins: FakePlugins) -> None:
    """Requirement: Intents are aggregated before connecting."""
    fake_plugins.add("Alpha", "import discord\nINTENTS = discord.Intents(members=True)\n")
    fake_plugins.add("Beta", "import discord\nINTENTS = discord.Intents(message_content=True)\n")
    expected = discord.Intents.default()
    expected.members = True
    expected.message_content = True

    intents = required_intents(discover(["Alpha", "Beta"], fake_plugins.entry_points))

    assert intents == expected


async def test_bot_uses_the_aggregated_intents(
    fake_plugins: FakePlugins, store: Store, tmp_path: Path
) -> None:
    """Requirement: Intents are aggregated before connecting."""
    fake_plugins.add("Alpha", "import discord\nINTENTS = discord.Intents(members=True)\n")

    bot = fake_plugins.bot(["Alpha"], tmp_path, store)

    assert bot.intents == required_intents(discover(["Alpha"], fake_plugins.entry_points))


@pytest.mark.parametrize("beta", ["async def setup(bot):\n    raise RuntimeError('broken')\n", ""])
async def test_one_plugin_fails(
    fake_plugins: FakePlugins,
    store: Store,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    beta: str,
) -> None:
    """Requirement: A failing plugin disables only itself."""
    fake_plugins.add("Alpha", RECORD)
    fake_plugins.add("Beta", beta)
    fake_plugins.add("Gamma", "DEPENDS = ('Beta',)\n" + RECORD)
    fake_plugins.add("Delta", RECORD)
    bot = fake_plugins.bot(["Alpha", "Beta", "Gamma", "Delta"], tmp_path, store)

    with caplog.at_level(logging.ERROR):
        failed = await bot.load_plugins()

    assert failed == ["Beta", "Gamma"]
    assert bot.loaded == ("Alpha", "Delta")
    assert fake_plugins.calls() == ["Alpha", "Delta"]
    assert "Beta" in caplog.text
    assert "Gamma" in caplog.text


async def test_first_load_creates_the_files(
    fake_plugins: FakePlugins, store: Store, tmp_path: Path
) -> None:
    """Requirement: Plugin files live under plugins/<Name>/."""
    fake_plugins.add("Alpha", CONFIGURED, BUNDLE)
    root = tmp_path / "plugins"

    assert await fake_plugins.bot(["Alpha"], root, store).load_plugins() == []

    directory = root / "Alpha"
    assert (directory / "config.yaml").read_text(encoding="utf-8") == "greeting: Hello\n"
    assert (directory / "lang" / "en-US" / "register.yaml").exists()
    assert fake_plugins.calls() == [("Hello", ("en-US",), directory, store)]


async def test_edited_files_are_kept_unless_renewal_is_forced(
    fake_plugins: FakePlugins, store: Store, tmp_path: Path
) -> None:
    """Requirement: Plugin files live under plugins/<Name>/."""
    fake_plugins.add("Alpha", CONFIGURED, BUNDLE)
    root = tmp_path / "plugins"
    await fake_plugins.bot(["Alpha"], root, store).load_plugins()
    config = root / "Alpha" / "config.yaml"
    register = root / "Alpha" / "lang" / "en-US" / "register.yaml"
    config.write_text("greeting: Hi\n", encoding="utf-8")
    register.write_text("greet:\n  name: hey\n", encoding="utf-8")

    await fake_plugins.bot(["Alpha"], root, store).load_plugins()
    kept = register.read_text(encoding="utf-8")
    await fake_plugins.bot(["Alpha"], root, store, force_lang=True).load_plugins()

    assert kept == "greet:\n  name: hey\n"
    assert register.read_text(encoding="utf-8") == "greet:\n  name: greet\n"
    assert config.read_text(encoding="utf-8") == "greeting: Hi\n"
    assert [call[0] for call in fake_plugins.calls() if isinstance(call, tuple)] == [
        "Hello",
        "Hi",
        "Hi",
    ]


async def test_broken_config_disables_the_plugin(
    fake_plugins: FakePlugins, store: Store, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Plugin files live under plugins/<Name>/."""
    fake_plugins.add("Alpha", CONFIGURED, BUNDLE)
    config = tmp_path / "plugins" / "Alpha" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("greeting: [1, 2]\n", encoding="utf-8")

    with caplog.at_level(logging.ERROR):
        failed = await fake_plugins.bot(["Alpha"], tmp_path / "plugins", store).load_plugins()

    assert failed == ["Alpha"]
    assert str(config) in caplog.text


async def test_unknown_context(store: Store, tmp_path: Path) -> None:
    """Requirement: Plugin files live under plugins/<Name>/."""
    bot = Bot([], root=tmp_path, store=store)

    with pytest.raises(PluginError, match="nowhere"):
        bot.plugin_context("nowhere")


PROBE = """
from discord.ext import commands


class Probe(commands.Cog):
    pass


async def setup(bot):
    await bot.add_cog(Probe())
"""


async def test_reload_with_dependents(
    fake_plugins: FakePlugins, store: Store, tmp_path: Path
) -> None:
    """Requirement: Hot reload follows dependencies and intents."""
    fake_plugins.add("Alpha", RECORD)
    fake_plugins.add("Beta", "DEPENDS = ('Alpha',)\n" + RECORD)
    fake_plugins.add("Gamma", RECORD)
    bot = fake_plugins.bot(["Alpha", "Beta", "Gamma"], tmp_path, store)
    await bot.load_plugins()

    loaded = len(fake_plugins.calls())

    assert await bot.reload_plugin("Alpha") == ["Alpha", "Beta"]

    assert fake_plugins.calls()[loaded:] == ["Alpha", "Beta"]
    with pytest.raises(PluginError, match="Delta"):
        await bot.reload_plugin("Delta")


async def test_failed_reload_keeps_the_previous_version(
    fake_plugins: FakePlugins, store: Store, tmp_path: Path
) -> None:
    """Requirement: Hot reload follows dependencies and intents."""
    module = fake_plugins.add("Alpha", PROBE)
    bot = fake_plugins.bot(["Alpha"], tmp_path, store)
    await bot.load_plugins()
    previous = bot.extensions[module]
    fake_plugins.replace("Alpha", "async def setup(bot):\n    raise RuntimeError('new code')\n")

    with pytest.raises(PluginError, match="Alpha"):
        await bot.reload_plugin("Alpha")

    assert bot.extensions[module] is previous
    assert bot.get_cog("Probe") is not None
    assert bot.loaded == ("Alpha",)


READS_A_FILE = """
from discord.ext import commands


class Probe(commands.Cog):
    pass


async def setup(bot):
    await bot.add_cog(Probe())
    (bot.plugin_context(__name__).directory / "data.txt").read_text(encoding="utf-8")
"""


# A file of the plugin that no longer validates, and what the reload's error says about it.
BROKEN_FILES = [
    ("config.yaml", "greeting: [not, text]\n", r"config\.yaml: greeting"),
    ("lang/en-US/register.yaml", "greet:\n  name: Greet\n", r"register\.yaml: greet\.name"),
]


@pytest.mark.parametrize("broken", BROKEN_FILES)
async def test_broken_files_keep_the_previous_version(
    fake_plugins: FakePlugins, store: Store, tmp_path: Path, broken: tuple[str, str, str]
) -> None:
    """Requirement: Hot reload follows dependencies and intents."""
    relative, text, error = broken
    module = fake_plugins.add("Alpha", CONFIGURED, BUNDLE)
    bot = fake_plugins.bot(["Alpha"], tmp_path, store)
    await bot.load_plugins()
    loaded = list(fake_plugins.calls())
    (tmp_path / "Alpha" / relative).write_text(text, encoding="utf-8")

    with pytest.raises(PluginError, match=rf"Alpha failed to reload: .*{error}"):
        await bot.reload_plugin("Alpha")

    # The previous version ran its setup again, with the config and lang it had.
    assert fake_plugins.calls() == [*loaded, *loaded]
    assert bot.loaded == ("Alpha",)
    assert module in bot.extensions


async def test_previous_version_fails_too(
    fake_plugins: FakePlugins, store: Store, tmp_path: Path
) -> None:
    """Requirement: Hot reload follows dependencies and intents."""
    module = fake_plugins.add("Alpha", READS_A_FILE)
    (tmp_path / "Alpha").mkdir()
    data = tmp_path / "Alpha" / "data.txt"
    data.write_text("data", encoding="utf-8")
    bot = fake_plugins.bot(["Alpha"], tmp_path, store)
    await bot.load_plugins()
    data.unlink()

    with pytest.raises(PluginError, match=r"Alpha failed to reload and is unloaded: .*data\.txt"):
        await bot.reload_plugin("Alpha")

    assert bot.loaded == ()
    assert module not in bot.extensions
    assert bot.get_cog("Probe") is None
    with pytest.raises(PluginError, match="no plugin loads from"):
        bot.plugin_context(module)
    data.write_text("data", encoding="utf-8")
    await bot.load_plugin(discover(["Alpha"], fake_plugins.entry_points)[0])
    assert bot.loaded == ("Alpha",)
    assert bot.get_cog("Probe") is not None


async def test_hot_load_needs_the_intents(
    fake_plugins: FakePlugins, store: Store, tmp_path: Path
) -> None:
    """Requirement: Hot reload follows dependencies and intents."""
    fake_plugins.add("Alpha", RECORD)
    fake_plugins.add("Members", "import discord\nINTENTS = discord.Intents(members=True)\n")
    child = fake_plugins.add("Child", RECORD)
    fake_plugins.add("Late", RECORD)
    bot = fake_plugins.bot(["Alpha"], tmp_path, store)
    await bot.load_plugins()
    (members, late) = discover(["Members", "Late"], fake_plugins.entry_points)

    with pytest.raises(PluginError, match="members"):
        await bot.load_plugin(members)
    with pytest.raises(PluginError, match="Beta"):
        await bot.load_plugin(PluginInfo("Child", child, depends=("Beta",)))
    await bot.load_plugin(late)
    with pytest.raises(PluginError, match="already"):
        await bot.load_plugin(late)

    assert bot.loaded == ("Alpha", "Late")
    assert fake_plugins.calls() == ["Alpha", "Late"]


TICKET = """
from xincord.core.component_ids import ComponentIds

from .. import calls

FIELDS = ("action", "sub_action", "color_index", "user_id", "msg_id", "btn_index")
IDS = ComponentIds("ticket", FIELDS, legacy_prefix="ticket@")


async def handle(interaction, fields):
    calls.append((interaction.data["custom_id"], dict(fields.fields), fields.legacy))


async def setup(bot):
    bot.route(__name__, IDS, handle)
"""
BROKEN_HANDLER = """
from xincord.core.component_ids import ComponentIds

IDS = ComponentIds("broken", ("action",))


async def handle(interaction, fields):
    raise RuntimeError("handler failed")


async def setup(bot):
    bot.route(__name__, IDS, handle)
"""


@dataclass
class FakeInteraction:
    type: discord.InteractionType
    data: dict[str, object]
    message: object = None
    user: object = field(default_factory=lambda: SimpleNamespace(name="alice"))


def interaction(
    custom_id: str, kind: discord.InteractionType = discord.InteractionType.component
) -> discord.Interaction:
    return cast("discord.Interaction", FakeInteraction(kind, {"custom_id": custom_id}))


async def test_routed_interactions(fake_plugins: FakePlugins, store: Store, tmp_path: Path) -> None:
    """Requirement: Component and modal interactions reach their plugin."""
    fake_plugins.add("Ticket", TICKET)
    bot = fake_plugins.bot(["Ticket"], tmp_path, store)
    await bot.load_plugins()

    await bot.on_interaction(interaction("ticket:1:a=press"))
    await bot.on_interaction(
        interaction("ticket@a:submit;f:1", discord.InteractionType.modal_submit)
    )

    assert fake_plugins.calls() == [
        ("ticket:1:a=press", {"action": "press"}, False),
        ("ticket@a:submit;f:1", {"action": "submit", "btn_index": "1"}, True),
    ]


async def test_unowned_and_failing_interactions(
    fake_plugins: FakePlugins, store: Store, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Component and modal interactions reach their plugin."""
    fake_plugins.add("Ticket", TICKET)
    fake_plugins.add("Broken", BROKEN_HANDLER)
    bot = fake_plugins.bot(["Ticket", "Broken"], tmp_path, store)
    await bot.load_plugins()

    await bot.on_interaction(interaction("other:1:a=x"))
    await bot.on_interaction(interaction("ticket:1:a=x", discord.InteractionType.autocomplete))
    with caplog.at_level(logging.ERROR):
        await bot.on_interaction(interaction("broken:1:a=x"))
        await bot.on_interaction(interaction("ticket:1:z=x"))

    assert fake_plugins.calls() == []
    assert "Broken" in caplog.text
    assert "Ticket" in caplog.text


async def test_reload_replaces_the_handler(
    fake_plugins: FakePlugins, store: Store, tmp_path: Path
) -> None:
    """Requirement: Routes follow the plugin's lifecycle."""
    fake_plugins.add("Ticket", TICKET)
    bot = fake_plugins.bot(["Ticket"], tmp_path, store)
    await bot.load_plugins()
    await bot.reload_plugin("Ticket")

    await bot.on_interaction(interaction("ticket:1:a=press"))

    assert len(fake_plugins.calls()) == 1


async def test_failed_load_leaves_no_route(
    fake_plugins: FakePlugins, store: Store, tmp_path: Path
) -> None:
    """Requirement: Routes follow the plugin's lifecycle."""
    fake_plugins.add(
        "Ticket",
        TICKET + "\n\nasync def setup(bot):\n    bot.route(__name__, IDS, handle)\n"
        "    raise RuntimeError('late failure')\n",
    )
    bot = fake_plugins.bot(["Ticket"], tmp_path, store)
    assert await bot.load_plugins() == ["Ticket"]

    await bot.on_interaction(interaction("ticket:1:a=press"))

    assert fake_plugins.calls() == []


LEGACY_BUTTON: dict[str, object] = {
    "type": 2,
    "style": 1,
    "custom_id": "ticket@a:press;f:0",
    "label": "Open",
}
LINK_BUTTON: dict[str, object] = {"type": 2, "style": 5, "url": "https://example.com"}


@dataclass
class FakeChannel:
    """Returns ``current`` from ``fetch_message``, or raises when it is None."""

    current: FakeMessage | None = None

    async def fetch_message(self, message_id: int) -> FakeMessage:
        if self.current is None or self.current.id != message_id:
            raise discord.NotFound(
                cast("ClientResponse", SimpleNamespace(status=404, reason="")), ""
            )
        return self.current


def row(*buttons: dict[str, object]) -> discord.Component:
    return discord.ActionRow(cast("ActionRowPayload", {"type": 1, "components": list(buttons)}))


@dataclass
class FakeMessage:
    components: Sequence[discord.Component]
    flags: discord.MessageFlags = field(default_factory=discord.MessageFlags)
    channel: FakeChannel = field(default_factory=FakeChannel)
    id: int = 42
    edits: list[discord.ui.View | discord.ui.LayoutView] = field(
        default_factory=list[discord.ui.View | discord.ui.LayoutView]
    )

    async def edit(self, *, view: discord.ui.View | discord.ui.LayoutView) -> None:
        self.edits.append(view)


def legacy_click(message: FakeMessage) -> discord.Interaction:
    return cast(
        "discord.Interaction",
        FakeInteraction(
            discord.InteractionType.component, {"custom_id": LEGACY_BUTTON["custom_id"]}, message
        ),
    )


async def loaded_ticket(fake_plugins: FakePlugins, store: Store, tmp_path: Path) -> Bot:
    fake_plugins.add("Ticket", TICKET)
    bot = fake_plugins.bot(["Ticket"], tmp_path, store)
    await bot.load_plugins()
    return bot


def ids_of(view: discord.ui.View | discord.ui.LayoutView) -> list[str | None]:
    return [item.custom_id for item in view.walk_children() if isinstance(item, discord.ui.Button)]


async def test_panel_is_upgraded(fake_plugins: FakePlugins, store: Store, tmp_path: Path) -> None:
    """Requirement: Legacy IDs are upgraded after use."""
    bot = await loaded_ticket(fake_plugins, store, tmp_path)
    message = FakeMessage([row(LEGACY_BUTTON, LINK_BUTTON)])
    message.channel.current = message

    await bot.on_interaction(legacy_click(message))

    (view,) = message.edits
    assert type(view) is discord.ui.View
    assert ids_of(view) == ["ticket:1:a=press;f=0", None]
    assert view.is_finished()


async def test_components_v2_message_is_upgraded(
    fake_plugins: FakePlugins, store: Store, tmp_path: Path
) -> None:
    """Requirement: Legacy IDs are upgraded after use."""
    bot = await loaded_ticket(fake_plugins, store, tmp_path)
    container: dict[str, object] = {
        "type": 17,
        "components": [{"type": 1, "components": [LEGACY_BUTTON]}],
    }
    message = FakeMessage(
        [discord.Container(cast("ContainerPayload", container), None)],
        discord.MessageFlags(components_v2=True),
    )
    message.channel.current = message

    await bot.on_interaction(legacy_click(message))

    (view,) = message.edits
    assert type(view) is discord.ui.LayoutView
    assert ids_of(view) == ["ticket:1:a=press;f=0"]


async def test_nothing_to_upgrade(
    fake_plugins: FakePlugins,
    store: Store,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: Legacy IDs are upgraded after use."""
    bot = await loaded_ticket(fake_plugins, store, tmp_path)
    upgraded = {**LEGACY_BUTTON, "custom_id": "ticket:1:a=press;f=0"}
    stale = FakeMessage([row(LEGACY_BUTTON)])
    stale.channel.current = FakeMessage([row(upgraded)])
    ephemeral = FakeMessage(
        [row(LEGACY_BUTTON)],
        discord.MessageFlags(ephemeral=True),
    )
    deleted = FakeMessage([row(LEGACY_BUTTON)])

    with caplog.at_level(logging.ERROR):
        for message in (stale, ephemeral, deleted):
            await bot.on_interaction(legacy_click(message))

    assert stale.channel.current.edits == []
    assert ephemeral.edits == []
    assert deleted.edits == []
    assert "42" in caplog.text
    assert len(fake_plugins.calls()) == 3
