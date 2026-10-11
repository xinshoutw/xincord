"""The registration of ``/dynamic-voice-channel`` and its two subcommands."""

import shutil
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import discord
import pytest
from discord import app_commands

from discord_fakes import FakeGuild, FakeInteraction, FakeMember
from plugin_fakes import FIXTURES, golden, load_plugin
from xincord.plugins.dynamic_voice_channel.cog import VoiceChannelOption

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.command_tree import CommandTree
    from xincord.core.storage import Store
    from xincord.plugins.dynamic_voice_channel.cog import DynamicVoiceChannel

    # discord.py calls a cog command's function with the cog, its binding, and the options.
    type Callback = Callable[..., Awaitable[None]]

GOLDEN = golden("dynamic_voice_channel")
NAME = "dynamic-voice-channel"
GUILD = FakeGuild(10)
LOBBY = SimpleNamespace(
    id=30, name="Lobby", type=discord.ChannelType.voice, category_id=20, guild_id=10
)


def listed(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    """The entries of ``actual`` whose keys ``expected`` lists, in its options too."""
    found = {key: actual.get(key) for key in expected}
    if "options" in expected:
        options = cast("list[dict[str, Any]]", actual.get("options") or [])
        wanted = cast("list[dict[str, Any]]", expected["options"])
        if len(options) == len(wanted):
            found["options"] = [listed(*pair) for pair in zip(options, wanted, strict=True)]
    return found


async def test_command_payload(bot: Bot) -> None:
    """Requirement: The command is a localized administrator guild command."""
    global_payload, guild_payload = await cast("CommandTree", bot.tree).payloads()
    expected: list[dict[str, Any]] = GOLDEN["commands"]

    by_name = {entry["name"]: entry for entry in guild_payload}

    assert [listed(by_name.get(wanted["name"], {}), wanted) for wanted in expected] == expected
    assert [entry["name"] for entry in guild_payload] == [NAME]  # a guild command
    assert NAME not in {entry["name"] for entry in global_payload}


@pytest.mark.parametrize(
    ("subcommand", "options"),
    [("bind", (LOBBY, "A")), ("unbind", (LOBBY,))],
)
async def test_command_callbacks(
    bot: Bot, cog: DynamicVoiceChannel, subcommand: str, options: tuple[object, ...]
) -> None:
    """Requirement: The command is a localized administrator guild command."""
    group = bot.tree.get_command(NAME)
    assert isinstance(group, app_commands.Group)
    command = group.get_command(subcommand)
    assert isinstance(command, app_commands.Command)
    assert command.binding is cog
    data: dict[str, object] = {
        "type": 1,
        "name": NAME,
        "options": [{"type": 1, "name": subcommand}],
    }
    interaction = FakeInteraction(
        data, command=command, user=FakeMember(GUILD), guild=GUILD
    ).as_interaction()

    assert await cast("CommandTree", bot.tree).interaction_check(interaction)
    await cast("Callback", command.callback)(cog, interaction, *options)

    deferred, (method, _) = cast("FakeInteraction", interaction).sent
    assert deferred == ("response.defer", {"ephemeral": True, "thinking": True})
    assert method == "edit_original_response"


async def test_voice_channels_only() -> None:
    """Requirement: The command is a localized administrator guild command."""
    option = VoiceChannelOption()
    interaction = FakeInteraction({"type": 1, "name": NAME}).as_interaction()

    # Discord resolves the channel, which the transformer passes on as it is.
    assert await option.transform(interaction, LOBBY) is LOBBY
    assert option.type is discord.AppCommandOptionType.channel
    assert option.channel_types == [discord.ChannelType.voice]  # JDA's cast took voice only


def bind_options(payload: list[dict[str, Any]]) -> list[str]:
    """The names of the options of ``bind`` in a guild command payload."""
    group = next(entry for entry in payload if entry["name"] == NAME)
    bind = next(option for option in group["options"] if option["name"] == "bind")
    return [option["name"] for option in bind["options"]]


async def test_bind_has_one_format(bot: Bot) -> None:
    """Requirement: v3's second format is ignored."""
    _, guild_payload = await cast("CommandTree", bot.tree).payloads()

    assert bind_options(guild_payload) == ["channel", "format-name-1"]


async def test_v3_lang_files(store: Store, tmp_path: Path) -> None:
    """Requirement: v3's second format is ignored."""
    lang = tmp_path / "plugins" / "DynamicVoiceChannel" / "lang"
    for locale in ("en-US", "zh-TW"):
        (lang / locale).mkdir(parents=True)
        fixture = FIXTURES / "plugins" / "dynamic_voice_channel" / f"v3-register-{locale}.yaml"
        shutil.copy(fixture, lang / locale / "register.yaml")

    bot = await load_plugin("DynamicVoiceChannel", tmp_path / "plugins", store)
    _, guild_payload = await cast("CommandTree", bot.tree).payloads()

    assert "format-name-2" in (lang / "zh-TW" / "register.yaml").read_text(encoding="utf-8")
    assert bind_options(guild_payload) == ["channel", "format-name-1"]
