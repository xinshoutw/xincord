"""The settings menu's buttons and select menus, in v3's ID format too.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/Event.kt:97-107
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/ChatLogger.kt:31-37
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/ChatLogger.kt:61-117
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/ChatLogger.kt:229-277
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/JsonManager.kt:60-113
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/resources/info.yaml:9
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/resources/lang/en-US/message/modify-allow.yaml:1-20
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/resources/lang/en-US/message/delete.yaml:1-9
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
from xincord.plugins.chat_logger.cog import IDS, NAMESPACE
from xincord.plugins.listen_channels.settings import Setting
from xincord.plugins.listen_channels.store import ListenSettings

if TYPE_CHECKING:
    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.chat_logger.cog import ChatLogger

GOLDEN = golden("chat_logger")
LOCALES = {"en-US": discord.Locale.american_english, "zh-TW": discord.Locale.taiwan_chinese}
BUTTON, CHANNEL_SELECT = 2, 8  # component types


def settings(store: Store) -> ListenSettings:
    """ChatLogger's listen channel settings in ``store``."""
    return ListenSettings(store, NAMESPACE)


def component(
    custom_id: str, *, values: list[str] | None = None, locale: discord.Locale = LOCALES["en-US"]
) -> FakeInteraction:
    """An administrator uses the component ``custom_id`` of the ephemeral menu in a channel.

    A button, or with ``values`` the channel select menu, of the menu in channel 5 (chat-log) of
    guild 10.
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
        channel=FakeChannel(id=5, name="chat-log"),
    )
    interaction.message = FakeMessage(
        sent=interaction.sent, flags=discord.MessageFlags(ephemeral=True)
    )
    return interaction


async def use(cog: ChatLogger, interaction: FakeInteraction) -> None:
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


async def test_toggle(cog: ChatLogger, store: Store) -> None:
    """Requirement: The settings components change the settings."""
    await settings(store).add_channels(10, 5, "allow", [30])
    interaction = component("chat_logger:1:a=toggle_btn")

    await use(cog, interaction)

    assert await settings(store).read_setting(10, 5) == Setting(allow_mode=False, allow=(30,))
    edited = edit(interaction)
    assert fields_of(edited) == ["<BLOCK>", "<#30> (`30`)", "Empty"]
    assert isinstance(edited["view"], discord.ui.View)
    assert len(edited["view"].children) == 4  # v3's buttons again


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
@pytest.mark.parametrize("kind", ["allow", "block"])
async def test_modify_a_list(cog: ChatLogger, store: Store, locale: str, kind: str) -> None:
    """Requirement: The settings components change the settings."""
    pressed = component(f"chat_logger:1:a=modify_{kind}_btn", locale=LOCALES[locale])

    await use(cog, pressed)

    edited = edit(pressed)
    assert edited["embeds"] == ()  # v3 replaced the whole message with the select menu
    view = edited["view"]
    assert isinstance(view, discord.ui.View)
    [select] = view.children
    assert isinstance(select, discord.ui.ChannelSelect)
    assert select.custom_id == f"chat_logger:1:a=modify_{kind}_menu"
    assert select.placeholder == GOLDEN["select"][locale]
    limits = GOLDEN["select_limits"]
    assert (select.min_values, select.max_values) == (limits["min_values"], limits["max_values"])
    assert [kind.value for kind in select.channel_types] == limits["channel_types"]
    assert await store.keys(NAMESPACE) == []  # pressing the button changes nothing

    chosen = component(select.custom_id, values=["30", "20"], locale=LOCALES[locale])
    await use(cog, chosen)

    # v3's document, in the allow mode that the menu shows (v3 saved allow_mode false).
    lists = (
        {"allow": [30, 20], "block": []} if kind == "allow" else {"allow": [], "block": [30, 20]}
    )
    assert await store.get(NAMESPACE, "10") == {"5": {"allow_mode": True, **lists}}
    lines = "<#30> (`30`)\n<#20> (`20`)"
    empty = GOLDEN["menu"][locale]["embed"]["fields"][2]["value"]  # the locale's empty text
    assert fields_of(edit(chosen)) == (
        ["<ALLOW>", lines, empty] if kind == "allow" else ["<ALLOW>", empty, lines]
    )


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_delete(cog: ChatLogger, store: Store, locale: str) -> None:
    """Requirement: The settings components change the settings."""
    await settings(store).add_channels(10, 5, "allow", [30])
    await settings(store).add_channels(10, 6, "block", [31])
    interaction = component("chat_logger:1:a=delete_btn", locale=LOCALES[locale])

    await use(cog, interaction)

    # v3 deleted the guild's whole file, so channel 6 lost its settings at the next start.
    assert await settings(store).read_settings(10) == {6: Setting(block=(31,))}
    edited = edit(interaction)
    [embed] = cast("tuple[discord.Embed, ...]", edited["embeds"])
    assert embed_dict(embed) == GOLDEN["delete"][locale]
    assert edited["view"] is None  # no components left


async def test_v3_ids(bot: Bot, store: Store) -> None:
    """Requirement: The settings components change the settings."""
    old, new = component("chat-logger@a:toggle_btn"), component("chat_logger:1:a=toggle_btn")

    await bot.on_interaction(old.as_interaction())
    assert await settings(store).read_setting(10, 5) == Setting(allow_mode=False)
    await bot.on_interaction(new.as_interaction())
    assert await settings(store).read_setting(10, 5) == Setting(allow_mode=True)

    # The menu is ephemeral: the core does not upgrade its IDs, and the handler edits it once.
    assert [method for method, _ in old.sent] == ["response.edit_message"]
    assert IDS.upgrade("chat-logger@a:toggle_btn") == "chat_logger:1:a=toggle_btn"


@pytest.mark.parametrize(
    ("custom_id", "values"),
    [
        ("chat_logger:1:a=other", None),
        ("chat_logger:1:a=modify_allow_menu", None),  # a button with a select menu's action
        ("chat_logger:1:a=toggle_btn", ["30"]),  # a select menu with a button's action
        ("chat_logger:1:a=other", ["30"]),
    ],
)
async def test_other_actions(
    cog: ChatLogger, store: Store, custom_id: str, values: list[str] | None
) -> None:
    """Requirement: The settings components change the settings."""
    interaction = component(custom_id, values=values)

    await use(cog, interaction)

    assert interaction.sent == []
    assert await store.keys(NAMESPACE) == []
