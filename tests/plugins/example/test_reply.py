"""The reply to /example-command.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/_Example/src/main/kotlin/_example/_Example.kt:24-42
    XsDiscordBotKt@3a59607:Plugins/_Example/src/main/resources/lang/en-US/message/example.yaml:1-16
    XsDiscordBotKt@3a59607:Plugins/_Example/src/main/resources/lang/zh-TW/message/example.yaml:1-16
"""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import discord
import pytest

from discord_fakes import FakeInteraction, buttons, embed_dict
from plugin_fakes import golden, load_plugin
from xincord.plugins.example.cog import Example

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from xincord.core.storage import Store

GOLDEN = golden("example")
FIRST_ID = "example:1:a=count;b=0"


@dataclass(frozen=True)
class Edit:
    """What the plugin put into the deferred response."""

    content: str | None
    embeds: list[dict[str, Any]]
    buttons: list[tuple[str | None, str | None]]


async def run(
    cog: Example,
    option1: str,
    option2: int | None = None,
    *,
    locale: discord.Locale = discord.Locale.american_english,
    channel: object = None,
) -> Edit:
    """Run the command as alice and return the edit of its deferred response."""
    options: list[dict[str, object]] = [{"type": 3, "name": "option1", "value": option1}]
    if option2 is not None:
        options.append({"type": 4, "name": "option2", "value": option2})
    data = {"type": 1, "name": "example-command", "options": options}
    interaction = FakeInteraction(data, locale=locale, channel=channel)

    await cog.reply(interaction.as_interaction(), option1, option2)

    ((method, fields),) = interaction.sent
    assert method == "edit_original_response"
    embeds = cast("Sequence[discord.Embed]", fields["embeds"])
    return Edit(
        cast("str | None", fields["content"]),
        [embed_dict(embed) for embed in embeds],
        buttons(fields["view"]),
    )


async def test_both_options(cog: Example) -> None:
    """Requirement: The reply echoes the options."""
    edit = await run(cog, "first", 2)

    assert edit.embeds == [GOLDEN["reply"]["en-US"]]
    assert edit.buttons == [(GOLDEN["counter"]["en-US"].format(count=0), FIRST_ID)]


async def test_option2_omitted(cog: Example) -> None:
    """Requirement: The reply echoes the options."""
    edit = await run(cog, "first")

    assert edit.embeds[0]["fields"][1]["value"] == "none"


@pytest.mark.parametrize("locale", [discord.Locale.taiwan_chinese, discord.Locale.japanese])
async def test_locale_and_fallback(cog: Example, locale: discord.Locale) -> None:
    """Requirement: The reply echoes the options."""
    edit = await run(cog, "first", 2, locale=locale)

    assert edit.embeds == [GOLDEN["reply"]["zh-TW"]]
    assert edit.buttons == [(GOLDEN["counter"]["zh-TW"].format(count=0), FIRST_ID)]


async def test_command_placeholders(store: Store, tmp_path: Path) -> None:
    """Requirement: The reply echoes the options."""
    template = tmp_path / "plugins" / "_Example" / "lang" / "en-US" / "message" / "example.yaml"
    template.parent.mkdir(parents=True)
    template.write_text(
        'content: "%user_name% ran %command_string% as %bot_name%"\n', encoding="utf-8"
    )
    bot = await load_plugin("_Example", tmp_path / "plugins", store)
    cog = bot.get_cog("Example")
    assert isinstance(cog, Example)

    edit = await run(cog, "first")

    assert edit.content == "alice ran /example-command option1: first as xincord"


async def test_placeholder_text_in_an_option(cog: Example) -> None:
    """Requirement: The reply echoes the options."""
    text = "%bot_name% %_Example@option1%"

    edit = await run(cog, text)

    assert edit.embeds[0]["fields"][0]["value"] == text


async def test_command_in_a_thread(cog: Example) -> None:
    """Requirement: The reply echoes the options."""
    thread = SimpleNamespace(id=7, name="help")  # a channel without a category

    edit = await run(cog, "first", channel=thread)

    assert edit.embeds[0]["fields"][0]["value"] == "first"
