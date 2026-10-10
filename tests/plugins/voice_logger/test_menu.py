"""The settings menu that ``/voice-logger setting`` shows for the current channel.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/Event.kt:83-87
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:51-57
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:383-439
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/command/PlaceholderSerializer.kt:6-14
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/resources/lang/en-US/placeholder.yaml:1-3
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/resources/lang/en-US/message/voice-logger@setting.yaml:1-40
"""

from typing import TYPE_CHECKING, Any, cast

import discord
import pytest

from discord_fakes import FakeChannel, FakeGuild, FakeInteraction, FakeMember, embed_dict
from plugin_fakes import golden
from xincord.plugins.voice_logger.settings import list_text
from xincord.plugins.voice_logger.store import NAMESPACE

if TYPE_CHECKING:
    from xincord.core.storage import JSON, Store
    from xincord.plugins.voice_logger.cog import VoiceLogger

GOLDEN = golden("voice_logger")
XFAIL = pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The settings menu shows the channel's settings",
)
LOCALES = {"en-US": discord.Locale.american_english, "zh-TW": discord.Locale.taiwan_chinese}
LINE = "%allowlist_channel_mention% (`%allowlist_channel_id%`)\n"  # v3's allow_list_format
LONG = [1290000000000000000 + index for index in range(40)]  # 19-digit IDs


def command(channel: FakeChannel, locale: discord.Locale = LOCALES["en-US"]) -> FakeInteraction:
    """An administrator runs ``/voice-logger setting`` in ``channel`` of guild 10."""
    guild = FakeGuild(10)
    return FakeInteraction(
        {"name": "voice-logger", "type": 1, "options": [{"name": "setting", "type": 1}]},
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


@XFAIL
@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_menu(cog: VoiceLogger, store: Store, locale: str) -> None:
    """Requirement: The settings menu shows the channel's settings."""
    await store.put(NAMESPACE, "10", {"5": {"allow_mode": False, "allow": [30], "block": []}})
    interaction = command(FakeChannel(id=5, name="voice-log"), LOCALES[locale])

    await cog.show_settings(interaction.as_interaction())

    embed, buttons = edited(interaction)
    assert embed == GOLDEN["menu"][locale]["embed"]
    assert buttons == GOLDEN["menu"][locale]["buttons"]


@XFAIL
async def test_channel_without_settings(cog: VoiceLogger, store: Store) -> None:
    """Requirement: The settings menu shows the channel's settings."""
    interaction = command(FakeChannel(id=6, name="other"))

    await cog.show_settings(interaction.as_interaction())

    embed, _ = edited(interaction)
    assert [field["value"] for field in embed["fields"]] == ["<ALLOW>", "Empty", "Empty"]
    assert await store.keys(NAMESPACE) == []  # v3 kept the default in memory only


@XFAIL
async def test_long_list_in_the_menu(cog: VoiceLogger, store: Store) -> None:
    """Requirement: The settings menu shows the channel's settings."""
    # v3 threw for a field over 1024 characters, after saving, so the menu never opened again.
    document: dict[str, JSON] = {"5": {"allow_mode": True, "allow": [*LONG], "block": []}}
    await store.put(NAMESPACE, "10", document)
    interaction = command(FakeChannel(id=5, name="voice-log"))

    await cog.show_settings(interaction.as_interaction())

    embed, _ = edited(interaction)
    allowed = str(embed["fields"][1]["value"])
    assert len(allowed) <= 1024
    assert allowed.endswith("\n...")


@XFAIL
def test_list_text() -> None:
    """Requirement: The settings menu shows the channel's settings."""
    # v3 replaced the line's own keys, then expanded the others with the interaction's values.
    line = "%allowlist_channel_mention% (`%allowlist_channel_id%`) by %user_name%\n"
    values = {"user_name": "admin", "allowlist_channel_id": "ignored"}

    assert list_text([30, 20], line, "Empty", values, "allowlist") == (
        "<#30> (`30`) by admin\n<#20> (`20`) by admin\n"
    )
    assert list_text([30], "%blocklist_channel_id%;", "-", {}, "blocklist") == "30;"
    assert list_text([], line, "none for %user_name%", values, "allowlist") == "none for admin"


@XFAIL
def test_long_list() -> None:
    """Requirement: The settings menu shows the channel's settings."""
    text = list_text(LONG, LINE, "Empty", {}, "allowlist")

    # Each line has 47 characters with its newline: 21 of them fit before the ellipsis.
    lines = text.split("\n")
    assert lines == [f"<#{channel}> (`{channel}`)" for channel in LONG[:21]] + ["..."]
    assert len(text) == 21 * 47 + 3
    # Discord counts UTF-16 code units, where a character outside the BMP takes two: with 20
    # loudspeakers, a line takes 87 of them (67 characters), so 11 lines fit, not 15.
    wide = list_text(LONG, chr(0x1F50A) * 20 + LINE, "Empty", {}, "allowlist")
    assert wide.split("\n")[-1] == "..."
    assert len(wide.split("\n")) == 11 + 1
