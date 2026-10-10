"""Posting: each command's message goes to the channel, or else into the deferred response.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/SimpleCommand.kt:21-58
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/Event.kt:49-53
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/messagecreator/v2/MessageCreator.kt:84-95
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/placeholder/Placeholder.kt:15-18
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/lang/zh-TW/message/cub-none-card.yaml:1-16
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/lang/zh-TW/message/tsib-none-card.yaml:1-16
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/lang/zh-TW/message/ctcb-none-card.yaml:1-16
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/lang/zh-TW/message/ctcb-remit.yaml:1-17
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/lang/zh-TW/message/chpytwtp-remit.yaml:1-17
"""

import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import discord
import pytest

from discord_fakes import FakeChannel, FakeInteraction, buttons, embed_dict, forbidden
from plugin_fakes import golden, load_plugin
from xincord.plugins.simple_command.cog import SimpleCommand

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from discord_fakes import Sent
    from xincord.core.storage import Store

GOLDEN = golden("simple_command")
NAMES = ("cub-none-card", "tsib-none-card", "ctcb-none-card", "ctcb-remit", "chpytwtp-remit")
XFAIL = pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="A command posts its message in the channel"
)
LINK_BUTTON = """\
content: "Pay here"
components:
  - !ButtonsComponent
    buttons: [{style: 5, url: "https://pay.example", label: "Pay"}]
"""


class ClosingChannel(FakeChannel):
    """A channel that refuses every message after closing its files, as discord.py's send does."""

    async def send(self, **fields: object) -> None:
        """Close the message's files, then fail as Discord does without permissions."""
        for file in cast("Sequence[discord.File]", fields["files"]):
            file.close()
        raise forbidden()


def command(name: str, locale: discord.Locale, channel: object) -> FakeInteraction:
    """The interaction of command ``name``, sharing its record with a fake channel's."""
    sent: list[Sent] = channel.sent if isinstance(channel, FakeChannel) else []
    data = {"type": 1, "name": name}
    command = SimpleNamespace(name=name)
    return FakeInteraction(data, locale=locale, channel=channel, command=command, sent=sent)


async def run(
    cog: SimpleCommand,
    name: str = "cub-none-card",
    *,
    locale: discord.Locale = discord.Locale.american_english,
    channel: object = None,
) -> list[Sent]:
    """Run command ``name`` as alice in a fake channel; return what the plugin sent, in order."""
    interaction = command(name, locale, FakeChannel() if channel is None else channel)
    await cog.post_message(interaction.as_interaction())
    return interaction.sent


async def load_with(
    template: str,
    tmp_path: Path,
    store: Store,
    *,
    name: str = "cub-none-card",
    locale: str = "zh-TW",
) -> SimpleCommand:
    """Load the plugin with the operator's ``message/<name>.yaml`` in ``locale``."""
    message = tmp_path / "plugins" / "SimpleCommand" / "lang" / locale / "message"
    message.mkdir(parents=True)
    (message / f"{name}.yaml").write_text(template, encoding="utf-8")
    bot = await load_plugin("SimpleCommand", tmp_path / "plugins", store)
    cog = bot.get_cog("SimpleCommand")
    assert isinstance(cog, SimpleCommand)
    return cog


def gallery(image: Path) -> str:
    """A Components V2 template that shows the local file ``image``."""
    return (
        "is_components_v2: true\n"
        f"components_v2: [{{type: media_gallery, items: [{{file_path: '{image}'}}]}}]\n"
    )


def embeds(fields: dict[str, object]) -> list[dict[str, Any]]:
    """The embeds of a message, as dictionaries."""
    return [embed_dict(embed) for embed in cast("Sequence[discord.Embed]", fields["embeds"])]


def files(fields: dict[str, object], key: str) -> Sequence[discord.File]:
    """The files of a message under ``key``."""
    return cast("Sequence[discord.File]", fields[key])


@XFAIL
async def test_message(cog: SimpleCommand) -> None:
    """Requirement: A command posts its message in the channel."""
    sent = await run(cog)

    assert [method for method, _ in sent] == ["channel.send", "delete_original_response"]
    assert embeds(sent[0][1]) == [GOLDEN["messages"]["cub-none-card"]]


@XFAIL
@pytest.mark.parametrize("name", NAMES)
async def test_every_command(cog: SimpleCommand, name: str) -> None:
    """Requirement: A command posts its message in the channel."""
    sent = await run(cog, name)

    assert embeds(sent[0][1]) == [GOLDEN["messages"][name]]


@XFAIL
@pytest.mark.parametrize("locale", [discord.Locale.american_english, discord.Locale.japanese])
async def test_default_locale(cog: SimpleCommand, locale: discord.Locale) -> None:
    """Requirement: A command posts its message in the channel."""
    sent = await run(cog, "ctcb-remit", locale=locale)

    assert embeds(sent[0][1]) == [GOLDEN["messages"]["ctcb-remit"]]


@XFAIL
async def test_default_locale_over_an_operator_template(store: Store, tmp_path: Path) -> None:
    """Requirement: A command posts its message in the channel."""
    template = 'content: "en-US"\n'
    cog = await load_with(template, tmp_path, store, name="ctcb-remit", locale="en-US")

    sent = await run(cog, "ctcb-remit")

    assert sent[0][1]["content"] is None
    assert embeds(sent[0][1]) == [GOLDEN["messages"]["ctcb-remit"]]


@XFAIL
async def test_bot_placeholders(store: Store, tmp_path: Path) -> None:
    """Requirement: A command posts its message in the channel."""
    cog = await load_with('content: "%bot_name% (%bot_id%)"\n', tmp_path, store)

    sent = await run(cog)

    assert sent[0][1]["content"] == "xincord (99)"


@XFAIL
async def test_link_button(store: Store, tmp_path: Path) -> None:
    """Requirement: A command posts its message in the channel."""
    cog = await load_with(LINK_BUTTON, tmp_path, store)

    sent = await run(cog)

    assert sent[0][1]["content"] == "Pay here"
    assert buttons(sent[0][1]["view"]) == [("Pay", None)]


@XFAIL
async def test_layout_and_files(store: Store, tmp_path: Path) -> None:
    """Requirement: A command posts its message in the channel."""
    image = tmp_path / "qr.png"
    image.write_bytes(b"png")
    cog = await load_with(gallery(image), tmp_path, store)

    sent = await run(cog)

    posted = files(sent[0][1], "files")
    try:
        assert isinstance(sent[0][1]["view"], discord.ui.LayoutView)
        assert [file.filename for file in posted] == ["qr.png"]
    finally:
        for file in posted:
            file.close()


@XFAIL
async def test_channel_refuses_the_message(
    cog: SimpleCommand, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: A command posts its message in the channel."""
    with caplog.at_level(logging.WARNING):
        sent = await run(cog, channel=FakeChannel(error=forbidden()))

    assert [method for method, _ in sent] == ["edit_original_response"]
    assert embeds(sent[0][1]) == [GOLDEN["messages"]["cub-none-card"]]
    assert "cannot post cub-none-card" in caplog.text


@XFAIL
async def test_refused_files_are_rendered_again(store: Store, tmp_path: Path) -> None:
    """Requirement: A command posts its message in the channel."""
    image = tmp_path / "qr.png"
    image.write_bytes(b"png")
    cog = await load_with(gallery(image), tmp_path, store)

    sent = await run(cog, channel=ClosingChannel())

    ((method, fields),) = sent
    attached = files(fields, "attachments")
    try:
        assert method == "edit_original_response"
        assert [(file.filename, file.fp.closed) for file in attached] == [("qr.png", False)]
    finally:
        for file in attached:
            file.close()


@XFAIL
async def test_channel_without_messages(cog: SimpleCommand) -> None:
    """Requirement: A command posts its message in the channel."""
    forum = SimpleNamespace(id=6, name="questions")  # a forum or a category has no send

    sent = await run(cog, channel=forum)

    assert [method for method, _ in sent] == ["edit_original_response"]
    assert embeds(sent[0][1]) == [GOLDEN["messages"]["cub-none-card"]]
