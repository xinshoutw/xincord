"""The texts that v3 wrote in its code, per reader, and the control row's labels.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:783-821
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:784-854
"""

from typing import TYPE_CHECKING, cast

import discord
import pytest

from discord_fakes import FakeInteraction
from plugin_fakes import golden

if TYPE_CHECKING:
    from xincord.core.bot import Bot
    from xincord.plugins.ticket.cog import Ticket

GOLDEN = golden("ticket")
LABELS = ("lock", "unlock", "save", "delete")  # the control row's buttons


def ticket(bot: Bot) -> Ticket:
    """The loaded plugin's cog."""
    found = bot.get_cog("Ticket")
    assert found is not None
    return cast("Ticket", found)


@pytest.mark.parametrize(
    ("locale", "expected"), [("en-US", "en-US"), ("zh-TW", "zh-TW"), ("ja", "zh-TW")]
)
async def test_replies_in_the_users_locale(bot: Bot, locale: str, expected: str) -> None:
    """Requirement: Texts follow the reader."""
    interaction = FakeInteraction({}, locale=discord.Locale(locale))

    texts = ticket(bot).texts(interaction.as_interaction())

    # A locale without lang files falls back to zh-TW, as v3's templates did, and v3's texts were
    # Chinese for every locale.
    assert texts.get("error.not-found") == GOLDEN["texts"][expected]["not-found"]


async def test_public_texts_in_the_default_locale(bot: Bot) -> None:
    """Requirement: Texts follow the reader."""
    assert ticket(bot).public.get("control.lock") == GOLDEN["texts"]["zh-TW"]["lock"]


@pytest.mark.xfail(strict=True, reason="Texts follow the reader")
@pytest.mark.parametrize("locale", ["zh-TW", "en-US"])
async def test_control_row_labels(bot: Bot, locale: str) -> None:
    """Requirement: Texts follow the reader."""
    reader = FakeInteraction({}, locale=discord.Locale(locale))
    texts = ticket(bot).texts(reader.as_interaction())

    labels = {action: texts.get(f"control.{action}") for action in LABELS}

    # The owner's labels (2026-10-11), in both bundled files; v3's were its Kotlin strings.
    assert labels == GOLDEN["labels"][locale]


async def test_values_inserted_as_written(bot: Bot) -> None:
    """Requirement: Texts follow the reader."""
    texts = ticket(bot).public

    text = texts.get("reply.go-to-channel", {"tt@channel": "%tt@thread%", "tt@thread": "x"})

    assert text == GOLDEN["texts"]["zh-TW"]["go-to-placeholder"]
