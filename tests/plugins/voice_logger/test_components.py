"""The settings menu's buttons and select menus, in v3's ID format too.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/Event.kt:89-99
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:30-35
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:59-115
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:186-229
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/JsonManager.kt:60-113
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/resources/info.yaml:9
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/resources/lang/en-US/message/modify-allow.yaml:1-11
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/resources/lang/en-US/message/delete.yaml:1-9
"""

from typing import TYPE_CHECKING, Any, cast

import discord
import pytest

from discord_fakes import (
    FakeChannel,
    FakeGuild,
    FakeInteraction,
    FakeMember,
    FakeMessage,
    embed_dict,
)
from plugin_fakes import golden
from xincord.plugins.voice_logger.cog import IDS
from xincord.plugins.voice_logger.settings import Setting
from xincord.plugins.voice_logger.store import NAMESPACE, add_channels, read_setting, read_settings

if TYPE_CHECKING:
    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.voice_logger.cog import VoiceLogger

GOLDEN = golden("voice_logger")
XFAIL = pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The settings components change the settings",
)
LOCALES = {"en-US": discord.Locale.american_english, "zh-TW": discord.Locale.taiwan_chinese}
BUTTON, CHANNEL_SELECT = 2, 8  # component types


def component(
    custom_id: str,
    *,
    values: list[str] | None = None,
    locale: discord.Locale = LOCALES["en-US"],
    channel_id: int = 5,
) -> FakeInteraction:
    """An administrator uses the component ``custom_id`` of the ephemeral menu in a channel.

    A button, or with ``values`` the channel select menu, of the menu in channel ``channel_id``
    (voice-log) of guild 10.
    """
    guild = FakeGuild(10)
    data: dict[str, object] = {"custom_id": custom_id, "component_type": BUTTON}
    if values is not None:
        data |= {"component_type": CHANNEL_SELECT, "values": values}
    interaction = FakeInteraction(
        data,
        type=discord.InteractionType.component,
        locale=locale,
        user=FakeMember(guild, id=7, name="admin"),
        guild=guild,
        channel=FakeChannel(id=channel_id, name="voice-log"),
    )
    interaction.message = FakeMessage(
        sent=interaction.sent, flags=discord.MessageFlags(ephemeral=True)
    )
    return interaction


async def use(cog: VoiceLogger, interaction: FakeInteraction) -> None:
    """Hand ``interaction`` to the plugin's handler with its parsed ID, as the core does."""
    custom_id = str(interaction.data["custom_id"])
    await cog.handle(interaction.as_interaction(), IDS.parse(custom_id))


def edit(interaction: FakeInteraction) -> dict[str, Any]:
    """The fields of the only response: an edit of the menu's message."""
    [(method, fields)] = interaction.sent
    assert method == "response.edit_message"
    return fields


def fields_of(edited: dict[str, Any]) -> list[str]:
    """The field values of the edited message's only embed."""
    [embed] = cast("tuple[discord.Embed, ...]", edited["embeds"])
    return [str(field.value) for field in embed.fields]


@XFAIL
async def test_toggle(cog: VoiceLogger, store: Store) -> None:
    """Requirement: The settings components change the settings."""
    await add_channels(store, 10, 5, "allow", [30])
    interaction = component("voice_logger:1:a=toggle_btn")

    await use(cog, interaction)

    assert await read_setting(store, 10, 5) == Setting(allow_mode=False, allow=(30,))
    edited = edit(interaction)
    assert fields_of(edited) == ["<BLOCK>", "<#30> (`30`)", "Empty"]
    assert isinstance(edited["view"], discord.ui.View)
    assert len(edited["view"].children) == 4  # v3's buttons again


@XFAIL
@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
@pytest.mark.parametrize("kind", ["allow", "block"])
async def test_modify_a_list(cog: VoiceLogger, store: Store, locale: str, kind: str) -> None:
    """Requirement: The settings components change the settings."""
    pressed = component(f"voice_logger:1:a=modify_{kind}_btn", locale=LOCALES[locale])

    await use(cog, pressed)

    edited = edit(pressed)
    assert edited["embeds"] == ()  # v3 replaced the whole message with the select menu
    view = edited["view"]
    assert isinstance(view, discord.ui.View)
    [select] = view.children
    assert isinstance(select, discord.ui.ChannelSelect)
    assert select.custom_id == f"voice_logger:1:a=modify_{kind}_menu"
    assert select.placeholder == GOLDEN["select"][locale]
    limits = GOLDEN["select_limits"]
    assert (select.min_values, select.max_values) == (limits["min_values"], limits["max_values"])
    assert [kind.value for kind in select.channel_types] == limits["channel_types"]
    assert await store.keys(NAMESPACE) == []  # pressing the button changes nothing

    chosen = component(select.custom_id, values=["30", "20"], locale=LOCALES[locale])
    await use(cog, chosen)

    stored = await read_setting(store, 10, 5)
    assert (stored.allow if kind == "allow" else stored.block) == (30, 20)
    lines = "<#30> (`30`)\n<#20> (`20`)"
    empty = GOLDEN["menu"][locale]["embed"]["fields"][2]["value"]  # the locale's empty text
    assert fields_of(edit(chosen)) == (
        ["<ALLOW>", lines, empty] if kind == "allow" else ["<ALLOW>", empty, lines]
    )


@XFAIL
@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_delete(cog: VoiceLogger, store: Store, locale: str) -> None:
    """Requirement: The settings components change the settings."""
    await add_channels(store, 10, 5, "allow", [30])
    await add_channels(store, 10, 6, "block", [31])
    interaction = component("voice_logger:1:a=delete_btn", locale=LOCALES[locale])

    await use(cog, interaction)

    # v3 deleted the guild's whole file, so channel 6 lost its settings at the next start.
    assert await read_settings(store, 10) == {6: Setting(block=(31,))}
    edited = edit(interaction)
    [embed] = cast("tuple[discord.Embed, ...]", edited["embeds"])
    assert embed_dict(embed) == GOLDEN["delete"][locale]
    assert edited["view"] is None  # no components left


@pytest.mark.xfail(strict=True, reason="The settings components change the settings")
async def test_v3_ids(bot: Bot, store: Store) -> None:
    """Requirement: The settings components change the settings."""
    old, new = component("voice-logger@a:toggle_btn"), component("voice_logger:1:a=toggle_btn")

    await bot.on_interaction(old.as_interaction())
    assert await read_setting(store, 10, 5) == Setting(allow_mode=False)
    await bot.on_interaction(new.as_interaction())
    assert await read_setting(store, 10, 5) == Setting(allow_mode=True)

    # The menu is ephemeral: the core does not upgrade its IDs, and the handler edits it once.
    assert [method for method, _ in old.sent] == ["response.edit_message"]
    assert IDS.upgrade("voice-logger@a:toggle_btn") == "voice_logger:1:a=toggle_btn"


@XFAIL
@pytest.mark.parametrize(
    ("custom_id", "values"),
    [
        ("voice_logger:1:a=other", None),
        ("voice_logger:1:a=modify_allow_menu", None),  # a button with a select menu's action
        ("voice_logger:1:a=toggle_btn", ["30"]),  # a select menu with a button's action
        ("voice_logger:1:a=other", ["30"]),
    ],
)
async def test_other_actions(
    cog: VoiceLogger, store: Store, custom_id: str, values: list[str] | None
) -> None:
    """Requirement: The settings components change the settings."""
    interaction = component(custom_id, values=values)

    await use(cog, interaction)

    assert interaction.sent == []
    assert await store.keys(NAMESPACE) == []
