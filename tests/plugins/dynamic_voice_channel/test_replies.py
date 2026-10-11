"""``bind`` and ``unbind``: administrators bind voice channels as lobbies."""

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import discord
import pytest

from discord_fakes import FakeGuild, FakeInteraction, FakeMember, embed_dict
from plugin_fakes import golden, load_plugin
from xincord.plugins.dynamic_voice_channel.store import NAMESPACE, Binding, bind, read_bindings

if TYPE_CHECKING:
    from pathlib import Path

    from discord import app_commands

    from xincord.core.storage import Store
    from xincord.plugins.dynamic_voice_channel.cog import DynamicVoiceChannel

GOLDEN = golden("dynamic_voice_channel")
LOCALES = ["en-US", "zh-TW"]
GUILD = FakeGuild(10)
ADMIN = FakeMember(GUILD, id=1, name="alice")


def lobby(category_id: int | None = 20, name: str = "Lobby") -> app_commands.AppCommandChannel:
    """The ``channel`` option as Discord resolves it: voice channel 30."""
    channel = SimpleNamespace(
        id=30, name=name, type=discord.ChannelType.voice, category_id=category_id, guild_id=10
    )
    return cast("app_commands.AppCommandChannel", channel)


def run(subcommand: str, locale: str = "en-US") -> FakeInteraction:
    """``/dynamic-voice-channel <subcommand>`` run by an administrator in guild 10."""
    data: dict[str, object] = {
        "type": 1,
        "name": "dynamic-voice-channel",
        "options": [{"type": 1, "name": subcommand}],
    }
    return FakeInteraction(
        data,
        locale=discord.Locale(locale),
        user=ADMIN,
        guild=GUILD,
        guild_locale=discord.Locale.taiwan_chinese,
        permissions=discord.Permissions(administrator=True),
    )


def replied(interaction: FakeInteraction) -> dict[str, Any]:
    """The embed of the one edit of the deferred response."""
    [(method, fields)] = interaction.sent
    assert method == "edit_original_response"
    assert fields["content"] == ""
    [embed] = cast("tuple[discord.Embed, ...]", fields["embeds"])
    return embed_dict(embed)


@pytest.mark.parametrize("locale", LOCALES)
async def test_bind(cog: DynamicVoiceChannel, store: Store, locale: str) -> None:
    """Requirement: Administrators bind lobbies."""
    interaction = run("bind", locale)

    await cog.bind_lobby(interaction.as_interaction(), lobby(), "A")

    assert await read_bindings(store, 10) == [Binding(20, "Lobby", "A")]
    assert replied(interaction) == GOLDEN["replies"][locale]["bind-success"]  # the user's locale


async def test_bind_again(cog: DynamicVoiceChannel, store: Store) -> None:
    """Requirement: Administrators bind lobbies."""
    await bind(store, 10, Binding(20, "Lobby", "A"))
    await bind(store, 10, Binding(20, "Other", "C"))
    interaction = run("bind")

    await cog.bind_lobby(interaction.as_interaction(), lobby(), "E")

    assert await read_bindings(store, 10) == [
        Binding(20, "Other", "C"),
        Binding(20, "Lobby", "E"),
    ]
    assert replied(interaction) == GOLDEN["replies"]["en-US"]["bind-success"]


@pytest.mark.parametrize("locale", LOCALES)
async def test_bind_outside_a_category(cog: DynamicVoiceChannel, store: Store, locale: str) -> None:
    """Requirement: Administrators bind lobbies."""
    interaction = run("bind", locale)

    await cog.bind_lobby(interaction.as_interaction(), lobby(category_id=None), "A")

    assert await store.keys(NAMESPACE) == []
    assert replied(interaction) == GOLDEN["replies"][locale]["must-under-category"]


async def test_replies_get_the_interactions_values(store: Store, tmp_path: Path) -> None:
    """Requirement: Administrators bind lobbies."""
    # An operator's template with v3's Placeholder.get(event) keys.
    path = tmp_path / "plugins" / "DynamicVoiceChannel" / "lang" / "en-US" / "message"
    path.mkdir(parents=True)
    title = "%user_name% ran %full_command_name% (%bot_name%)"
    (path / "bind-success.yaml").write_text(
        f'embeds:\n  - title:\n      text: "{title}"\n', encoding="utf-8"
    )
    bot = await load_plugin("DynamicVoiceChannel", tmp_path / "plugins", store)
    cog = cast("DynamicVoiceChannel", bot.get_cog("DynamicVoiceChannel"))
    interaction = run("bind")

    await cog.bind_lobby(interaction.as_interaction(), lobby(), "A")

    assert replied(interaction)["title"] == "alice ran dynamic-voice-channel bind (xincord)"


@pytest.mark.parametrize("locale", LOCALES)
async def test_unbind(cog: DynamicVoiceChannel, store: Store, locale: str) -> None:
    """Requirement: Administrators unbind lobbies."""
    await bind(store, 10, Binding(20, "Lobby", "A"))
    await bind(store, 10, Binding(21, "Lobby", "C"))
    first, second = run("unbind", locale), run("unbind", locale)

    await cog.unbind_lobby(first.as_interaction(), lobby())
    await cog.unbind_lobby(second.as_interaction(), lobby())

    assert await read_bindings(store, 10) == [Binding(21, "Lobby", "C")]
    assert replied(first) == GOLDEN["replies"][locale]["unbind-success"]
    assert replied(second) == GOLDEN["replies"][locale]["unbind-fail"]


async def test_unbind_matches_the_current_name(cog: DynamicVoiceChannel, store: Store) -> None:
    """Requirement: Administrators unbind lobbies."""
    # As in v3, a lobby renamed since it was bound no longer names its binding.
    await bind(store, 10, Binding(20, "Lobby", "A"))
    interaction = run("unbind")

    await cog.unbind_lobby(interaction.as_interaction(), lobby(name="Renamed"))

    assert await read_bindings(store, 10) == [Binding(20, "Lobby", "A")]
    assert replied(interaction) == GOLDEN["replies"]["en-US"]["unbind-fail"]


@pytest.mark.parametrize("locale", LOCALES)
async def test_unbind_outside_a_category(
    cog: DynamicVoiceChannel, store: Store, locale: str
) -> None:
    """Requirement: Administrators unbind lobbies."""
    await bind(store, 10, Binding(20, "Lobby", "A"))
    interaction = run("unbind", locale)

    await cog.unbind_lobby(interaction.as_interaction(), lobby(category_id=None))

    assert await read_bindings(store, 10) == [Binding(20, "Lobby", "A")]
    assert replied(interaction) == GOLDEN["replies"][locale]["must-under-category"]


async def test_outside_a_guild(cog: DynamicVoiceChannel, store: Store) -> None:
    """Requirement: The command is a localized administrator guild command."""
    # Guild commands never run outside a guild; v3's handler assumed a guild too.
    bind_command, unbind_command = run("bind"), run("unbind")
    bind_command.guild = unbind_command.guild = None

    await cog.bind_lobby(bind_command.as_interaction(), lobby(), "A")
    await cog.unbind_lobby(unbind_command.as_interaction(), lobby())

    assert bind_command.sent == unbind_command.sent == []
    assert await store.keys(NAMESPACE) == []
