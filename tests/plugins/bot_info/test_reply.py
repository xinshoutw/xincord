"""The reply to /bot-info.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/kotlin/botinfo/BotInfo.kt:23-37
    XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/resources/lang/en-US/message/bot-info.yaml:1-17
    XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/resources/lang/zh-TW/message/bot-info.yaml:1-17
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Placeholder.kt:15-18
"""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import discord
import pytest

from discord_fakes import BOT_USER, FakeGuild, FakeInteraction, embed_dict
from plugin_fakes import golden, load_plugin

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.bot_info.cog import BotInfo

XFAIL = pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The reply shows the counts and the source link",
)
GOLDEN = golden("bot_info")
GUILDS = (FakeGuild(10, member_count=3), FakeGuild(20, member_count=4))


@dataclass(frozen=True)
class Edit:
    """What the plugin put into the deferred response."""

    content: str | None
    embeds: list[dict[str, Any]]


def loaded_cog(bot: Bot) -> BotInfo:
    """The cog of a plugin loaded in the test (no isinstance check: see the cog fixture)."""
    cog = bot.get_cog("BotInfo")
    assert cog is not None
    return cast("BotInfo", cog)


async def run(
    cog: BotInfo,
    guilds: Sequence[FakeGuild] = GUILDS,
    *,
    locale: discord.Locale = discord.Locale.american_english,
) -> Edit:
    """Run the command as alice while the bot is in ``guilds``; return the edit of its response."""
    client = SimpleNamespace(user=BOT_USER, guilds=list(guilds))
    interaction = FakeInteraction({"type": 1, "name": "bot-info"}, locale=locale, client=client)

    await cog.bot_info(interaction.as_interaction())

    ((method, fields),) = interaction.sent
    assert method == "edit_original_response"
    embeds = cast("Sequence[discord.Embed]", fields["embeds"])
    return Edit(cast("str | None", fields["content"]), [embed_dict(embed) for embed in embeds])


def counted(edit: Edit) -> list[str]:
    """The values of the server and member fields."""
    return [field["value"] for field in edit.embeds[0]["fields"][:2]]


@XFAIL
async def test_reply(cog: BotInfo) -> None:
    """Requirement: The reply shows the counts and the source link."""
    edit = await run(cog)

    assert edit.embeds == [GOLDEN["reply"]["en-US"]]


@XFAIL
@pytest.mark.parametrize(
    "locale",
    [discord.Locale.taiwan_chinese, discord.Locale.japanese, discord.Locale.british_english],
)
async def test_locale_and_fallback(cog: BotInfo, locale: discord.Locale) -> None:
    """Requirement: The reply shows the counts and the source link."""
    edit = await run(cog, locale=locale)

    assert edit.embeds == [GOLDEN["reply"]["zh-TW"]]


@XFAIL
async def test_operator_url_in_the_reply(store: Store, tmp_path: Path) -> None:
    """Requirement: The reply shows the counts and the source link."""
    config = 'source_url: "https://git.example/bot"\n'
    bot = await load_plugin("BotInfo", tmp_path / "plugins", store, config=config)

    edit = await run(loaded_cog(bot))

    assert edit.embeds[0]["fields"][2]["value"] == "https://git.example/bot"


@XFAIL
async def test_bot_placeholders(store: Store, tmp_path: Path) -> None:
    """Requirement: The reply shows the counts and the source link."""
    template = tmp_path / "plugins" / "BotInfo" / "lang" / "en-US" / "message" / "bot-info.yaml"
    template.parent.mkdir(parents=True)
    template.write_text('content: "%bot_name% (%bot_id%)"\n', encoding="utf-8")
    bot = await load_plugin("BotInfo", tmp_path / "plugins", store)

    edit = await run(loaded_cog(bot))

    assert edit.content == "xincord (99)"


@XFAIL
async def test_counts_at_each_use(cog: BotInfo) -> None:
    """Requirement: The reply shows the counts and the source link."""
    first = await run(cog)
    second = await run(cog, [*GUILDS, FakeGuild(30, member_count=5)])

    assert counted(first) == ["2", "7"]
    assert counted(second) == ["3", "12"]
