"""The settings menu that ``/chat-logger setting`` shows for the current channel.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/Event.kt:91-95
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/ChatLogger.kt:53-59
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/ChatLogger.kt:320-375
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/command/PlaceholderSerializer.kt:6-14
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/resources/lang/en-US/placeholder.yaml:1-3
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/resources/lang/en-US/message/chat-logger@setting.yaml:1-40
"""

from typing import TYPE_CHECKING, Any, cast

import discord
import pytest

from discord_fakes import FakeChannel, FakeGuild, FakeInteraction, FakeMember, embed_dict
from plugin_fakes import golden
from xincord.plugins.chat_logger.cog import NAMESPACE

if TYPE_CHECKING:
    from xincord.core.storage import JSON, Store
    from xincord.plugins.chat_logger.cog import ChatLogger

GOLDEN = golden("chat_logger")
LOCALES = {"en-US": discord.Locale.american_english, "zh-TW": discord.Locale.taiwan_chinese}
LONG = [1290000000000000000 + index for index in range(40)]  # 19-digit IDs


def command(channel: FakeChannel, locale: discord.Locale = LOCALES["en-US"]) -> FakeInteraction:
    """An administrator runs ``/chat-logger setting`` in ``channel`` of guild 10."""
    guild = FakeGuild(10)
    return FakeInteraction(
        {"name": "chat-logger", "type": 1, "options": [{"name": "setting", "type": 1}]},
        locale=locale,
        user=FakeMember(guild, id=7, name="admin"),
        guild=guild,
        channel=channel,
        permissions=discord.Permissions(administrator=True),
    )


def edited(interaction: FakeInteraction) -> tuple[dict[str, Any], list[list[object]]]:
    """The embed and the buttons (label, style, custom ID) of the only edit of the response."""
    [(method, fields)] = interaction.sent
    assert method == "edit_original_response"
    [embed] = cast("tuple[discord.Embed, ...]", fields["embeds"])
    view = fields["view"]
    assert isinstance(view, discord.ui.View)
    buttons: list[list[object]] = [
        [item.label, item.style.value, item.custom_id]
        for item in view.children
        if isinstance(item, discord.ui.Button)
    ]
    return embed_dict(embed), buttons


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_menu(cog: ChatLogger, store: Store, locale: str) -> None:
    """Requirement: The settings menu shows the channel's settings."""
    await store.put(NAMESPACE, "10", {"5": {"allow_mode": False, "allow": [30], "block": []}})
    interaction = command(FakeChannel(id=5, name="chat-log"), LOCALES[locale])

    await cog.show_settings(interaction.as_interaction())

    embed, buttons = edited(interaction)
    assert embed == GOLDEN["menu"][locale]["embed"]
    assert buttons == GOLDEN["menu"][locale]["buttons"]


async def test_channel_without_settings(cog: ChatLogger, store: Store) -> None:
    """Requirement: The settings menu shows the channel's settings."""
    interaction = command(FakeChannel(id=6, name="other"))

    await cog.show_settings(interaction.as_interaction())

    embed, _ = edited(interaction)
    assert [field["value"] for field in embed["fields"]] == ["<ALLOW>", "Empty", "Empty"]
    assert await store.keys(NAMESPACE) == []  # v3 kept the default in memory only


async def test_long_list(cog: ChatLogger, store: Store) -> None:
    """Requirement: The settings menu shows the channel's settings."""
    # v3 threw for a field over 1024 characters, after saving, so the menu never opened again.
    document: dict[str, JSON] = {"5": {"allow_mode": True, "allow": [*LONG], "block": []}}
    await store.put(NAMESPACE, "10", document)
    interaction = command(FakeChannel(id=5, name="chat-log"))

    await cog.show_settings(interaction.as_interaction())

    embed, _ = edited(interaction)
    allowed = str(embed["fields"][1]["value"])
    assert len(allowed) <= 1024
    assert allowed.endswith("\n...")
    assert allowed.split("\n", maxsplit=1)[0] == f"<#{LONG[0]}> (`{LONG[0]}`)"  # whole lines
