"""The bind and unbind commands: access, bindings and replies.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/WelcomeByeGuild.kt:59-76
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/WelcomeByeGuild.kt:120-303
    XsDiscordBotKt@3a59607:Plugins/WelcomeByeGuild/src/main/kotlin/welcomebyeguild/WelcomeByeGuildMessageKeys.kt:3-20
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/messagecreator/v2/MessageCreator.kt:130-134
"""

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import discord
import pytest

from discord_fakes import FakeChannel, FakeGuild, FakeInteraction, FakeMember, FakeUser
from plugin_fakes import golden
from xincord.plugins.welcome_goodbye.store import NAMESPACE, Bindings, read, set_channel

if TYPE_CHECKING:
    from discord import app_commands

    from xincord.core.storage import JSON, Store
    from xincord.plugins.welcome_goodbye.cog import WelcomeGoodbye

GOLDEN = golden("welcome_goodbye")
ADMINISTRATOR = discord.Permissions(administrator=True)
EN = discord.Locale.american_english
ZH = discord.Locale.taiwan_chinese


def make_guild() -> FakeGuild:
    """Guild 10 with the text channels general (5) and other (6)."""
    channels = [FakeChannel(id=5, name="general"), FakeChannel(id=6, name="other")]
    return FakeGuild(10, "guild", channels=channels)


def channel(guild: FakeGuild, channel_id: int) -> FakeChannel:
    """The guild's channel with that ID."""
    found = guild.get_channel(channel_id)
    assert found is not None
    return found


def option(value: FakeChannel) -> app_commands.AppCommandChannel:
    """A channel as the ``channel`` option passes it."""
    return cast("app_commands.AppCommandChannel", value)


def command(
    name: str,
    guild: FakeGuild | None,
    *,
    where: object = None,
    permissions: discord.Permissions = ADMINISTRATOR,
    locale: discord.Locale = EN,
) -> FakeInteraction:
    """Command ``name`` run by alice in the channel ``where`` of ``guild`` (None: no guild).

    ``locale`` is the guild's preferred locale; alice's client is in zh-TW. Outside a guild,
    ``locale`` is alice's.
    """
    return FakeInteraction(
        {"type": 1, "name": name},
        command=SimpleNamespace(name=name),
        user=FakeUser() if guild is None else FakeMember(guild),
        channel=where,
        guild=guild,
        guild_locale=None if guild is None else locale,
        locale=locale if guild is None else ZH,
        permissions=permissions,
    )


def reply(interaction: FakeInteraction) -> str:
    """The content that the command put into its deferred response."""
    ((method, fields),) = interaction.sent
    assert method == "edit_original_response"
    assert fields["embeds"] == ()
    return cast("str", fields["content"])


async def bind(
    cog: WelcomeGoodbye,
    interaction: FakeInteraction,
    chosen: FakeChannel | None = None,
) -> str:
    """Run a bind command, with ``chosen`` as its option; return the reply."""
    await cog.bind_channel(interaction.as_interaction(), None if chosen is None else option(chosen))
    return reply(interaction)


async def unbind(cog: WelcomeGoodbye, interaction: FakeInteraction) -> str:
    """Run an unbind command; return the reply."""
    await cog.unbind_channel(interaction.as_interaction())
    return reply(interaction)


def spy_writes(store: Store, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record the keys that the store writes from now on."""
    writes: list[str] = []
    put = store.put

    async def recording(namespace: str, key: str, value: JSON) -> None:
        writes.append(key)
        await put(namespace, key, value)

    monkeypatch.setattr(store, "put", recording)
    return writes


async def test_option_channel(cog: WelcomeGoodbye, store: Store) -> None:
    """Requirement: Administrators bind a channel."""
    guild = make_guild()
    interaction = command("welcome-channel-bind", guild, where=channel(guild, 6))

    text = await bind(cog, interaction, channel(guild, 5))

    assert text == GOLDEN["replies"]["en-US"]["welcome-bind-success"]
    assert await read(store, 10) == Bindings(welcome=5)


async def test_command_channel(cog: WelcomeGoodbye, store: Store) -> None:
    """Requirement: Administrators bind a channel."""
    guild = make_guild()
    interaction = command("bye-channel-bind", guild, where=channel(guild, 5))

    text = await bind(cog, interaction)

    assert text == GOLDEN["replies"]["en-US"]["bye-bind-success"]
    assert await read(store, 10) == Bindings(bye=5)


async def test_already_bound(
    cog: WelcomeGoodbye, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: Administrators bind a channel."""
    guild = make_guild()
    await set_channel(store, 10, "welcome", 5)
    writes = spy_writes(store, monkeypatch)
    interaction = command("welcome-channel-bind", guild, where=channel(guild, 6))

    text = await bind(cog, interaction, channel(guild, 5))

    assert text == GOLDEN["replies"]["en-US"]["welcome-bind-already"]
    assert writes == []


@pytest.mark.parametrize(
    "kind",
    [
        discord.ChannelType.public_thread,
        discord.ChannelType.private_thread,
        discord.ChannelType.voice,  # its text chat
        discord.ChannelType.stage_voice,
        discord.ChannelType.news,  # an announcement channel
    ],
)
async def test_no_text_channel(
    cog: WelcomeGoodbye, store: Store, kind: discord.ChannelType
) -> None:
    """Requirement: Administrators bind a channel."""
    where = FakeChannel(id=7, name="elsewhere", type=kind)
    interaction = command("welcome-channel-bind", make_guild(), where=where)

    text = await bind(cog, interaction)

    assert text == GOLDEN["replies"]["en-US"]["invalid-channel"]
    assert await store.keys(NAMESPACE) == []


async def test_option_that_is_not_a_text_channel(cog: WelcomeGoodbye, store: Store) -> None:
    """Requirement: Administrators bind a channel."""
    guild = make_guild()
    news = FakeChannel(id=8, name="news", type=discord.ChannelType.news)
    interaction = command("bye-channel-bind", guild, where=channel(guild, 5))

    text = await bind(cog, interaction, news)

    assert text == GOLDEN["replies"]["en-US"]["invalid-channel"]
    assert await store.keys(NAMESPACE) == []


async def test_one_channel_for_both(cog: WelcomeGoodbye, store: Store) -> None:
    """Requirement: Administrators bind a channel."""
    guild = make_guild()
    general = channel(guild, 5)

    await bind(cog, command("welcome-channel-bind", guild, where=general))
    await bind(cog, command("bye-channel-bind", guild, where=general))

    assert await read(store, 10) == Bindings(welcome=5, bye=5)


async def test_nothing_bound(cog: WelcomeGoodbye, store: Store) -> None:
    """Requirement: Administrators unbind a channel."""
    text = await unbind(cog, command("bye-channel-unbind", make_guild()))

    assert text == GOLDEN["replies"]["en-US"]["bye-unbind-empty"]
    assert await store.keys(NAMESPACE) == []


async def test_unbind(cog: WelcomeGoodbye, store: Store) -> None:
    """Requirement: Administrators unbind a channel."""
    await set_channel(store, 10, "welcome", 5)
    await set_channel(store, 10, "bye", 6)

    text = await unbind(cog, command("welcome-channel-unbind", make_guild()))

    assert text == GOLDEN["replies"]["en-US"]["welcome-unbind-success"]
    assert await read(store, 10) == Bindings(welcome=0, bye=6)


async def test_deleted_channel(cog: WelcomeGoodbye, store: Store) -> None:
    """Requirement: Administrators unbind a channel."""
    await set_channel(store, 10, "welcome", 5)
    guild = FakeGuild(10, "guild")  # channel 5 was deleted

    text = await unbind(cog, command("welcome-channel-unbind", guild))

    assert text == GOLDEN["replies"]["en-US"]["welcome-unbind-success"]


@pytest.mark.parametrize("name", ["welcome-channel-bind", "bye-channel-unbind"])
async def test_member_without_administrator(cog: WelcomeGoodbye, store: Store, name: str) -> None:
    """Requirement: Only administrators change the channels."""
    await set_channel(store, 10, "bye", 6)
    guild = make_guild()
    permissions = discord.Permissions(manage_guild=True, manage_channels=True)
    interaction = command(name, guild, where=channel(guild, 5), permissions=permissions)

    if name.endswith("-unbind"):
        text = await unbind(cog, interaction)
    else:
        text = await bind(cog, interaction)

    assert text == GOLDEN["replies"]["en-US"]["no-permission"]
    assert await store.items(NAMESPACE) == {"10": {"welcomeChannelId": 0, "byeChannelId": 6}}


async def test_outside_a_guild(cog: WelcomeGoodbye, store: Store) -> None:
    """Requirement: Only administrators change the channels."""
    interaction = command("welcome-channel-unbind", None, locale=EN)

    text = await unbind(cog, interaction)

    assert text == GOLDEN["replies"]["en-US"]["guild-only"]
    assert await store.keys(NAMESPACE) == []


async def test_guild_locale(cog: WelcomeGoodbye) -> None:
    """Requirement: Replies use the guild's locale."""
    interaction = command("welcome-channel-unbind", make_guild(), locale=EN)

    assert await unbind(cog, interaction) == GOLDEN["replies"]["en-US"]["welcome-unbind-empty"]


@pytest.mark.parametrize("guild_locale", [discord.Locale.japanese, discord.Locale.british_english])
async def test_other_locales(cog: WelcomeGoodbye, guild_locale: discord.Locale) -> None:
    """Requirement: Replies use the guild's locale."""
    interaction = command("welcome-channel-unbind", make_guild(), locale=guild_locale)

    assert await unbind(cog, interaction) == GOLDEN["replies"]["zh-TW"]["welcome-unbind-empty"]


@pytest.mark.parametrize("locale", [EN, ZH])
async def test_every_reply(cog: WelcomeGoodbye, locale: discord.Locale) -> None:
    """Requirement: Replies use the guild's locale."""
    guild = make_guild()
    general = channel(guild, 5)
    replies: dict[str, str] = {}
    for kind in ("welcome", "bye"):
        name = f"{kind}-channel"
        replies[f"{kind}-unbind-empty"] = await unbind(
            cog, command(f"{name}-unbind", guild, locale=locale)
        )
        replies[f"{kind}-bind-success"] = await bind(
            cog, command(f"{name}-bind", guild, where=general, locale=locale)
        )
        replies[f"{kind}-bind-already"] = await bind(
            cog, command(f"{name}-bind", guild, where=general, locale=locale)
        )
        replies[f"{kind}-unbind-success"] = await unbind(
            cog, command(f"{name}-unbind", guild, locale=locale)
        )
    replies["invalid-channel"] = await bind(
        cog, command("welcome-channel-bind", guild, locale=locale)
    )
    replies["no-permission"] = await unbind(
        cog,
        command(
            "bye-channel-unbind",
            guild,
            locale=locale,
            permissions=discord.Permissions.none(),
        ),
    )
    replies["guild-only"] = await unbind(cog, command("bye-channel-unbind", None, locale=locale))

    assert replies == GOLDEN["replies"][locale.value]
