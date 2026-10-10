"""Leaving a guild forgets its panels and its drafts, at once or when the bot is ready again.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Event.kt:85-88
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/Ticket.kt:243-245
    XsDiscordBotKt@3a59607:Plugins/Ticket/src/main/kotlin/ticket/create/StepManager.kt:329-331
"""

import logging
from typing import TYPE_CHECKING

import pytest

from discord_fakes import FakeGuild
from plugin_fakes import dispatch, load_plugin
from xincord.core.bot import Bot
from xincord.plugins.ticket.cog import Session
from xincord.plugins.ticket.model import Draft
from xincord.plugins.ticket.store import NAMESPACE

if TYPE_CHECKING:
    from pathlib import Path

    from conftest import Scene
    from xincord.core.storage import JSON, Store

DOCUMENT: JSON = {"500": [{"reasonTitle": "Why?", "adminIds": [3], "categoryId": 0}]}


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Leaving a guild forgets its panels"
)
async def test_leaving(scene: Scene) -> None:
    """Requirement: Leaving a guild forgets its panels."""
    await scene.store.put(NAMESPACE, "10", DOCUMENT)
    await scene.store.put(NAMESPACE, "11", DOCUMENT)
    scene.keep(Draft("Why?"))  # user 7's draft in guild 10
    scene.cog.drafts[8, 10] = Session(44, Draft("Mine"))
    scene.cog.drafts[7, 11] = Session(45, Draft("Elsewhere"))

    await dispatch(scene.bot, "guild_remove", FakeGuild(10).as_guild())

    # v3 deleted the guild's file and kept the user's step.
    assert await scene.store.get(NAMESPACE, "10") is None
    assert await scene.store.get(NAMESPACE, "11") == DOCUMENT
    assert scene.cog.drafts == {(7, 11): Session(45, Draft("Elsewhere"))}


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Leaving a guild forgets its panels"
)
async def test_left_while_offline(
    scene: Scene, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Leaving a guild forgets its panels."""
    for key in ("10", "11", "notes"):
        await scene.store.put(NAMESPACE, key, DOCUMENT)
    monkeypatch.setattr(scene.bot, "get_guild", {10: FakeGuild(10).as_guild()}.get)

    with caplog.at_level(logging.INFO):
        await dispatch(scene.bot, "ready")

    assert await scene.store.get(NAMESPACE, "11") is None
    assert await scene.store.get(NAMESPACE, "10") == DOCUMENT
    assert await scene.store.get(NAMESPACE, "notes") == DOCUMENT  # no guild ID: left alone
    assert "Ticket deleted the panels of guild 11, which the bot left" in caplog.text
    assert "Ticket ignores the panels stored under 'notes', which is no guild ID" in caplog.text


@pytest.mark.xfail(strict=True, reason="Leaving a guild forgets its panels")
async def test_loaded_into_a_ready_bot(
    store: Store, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: Leaving a guild forgets its panels."""
    await store.put(NAMESPACE, "11", DOCUMENT)

    def is_ready(_bot: Bot) -> bool:
        return True

    def get_guild(_bot: Bot, guild_id: int, /) -> FakeGuild | None:
        return {10: FakeGuild(10)}.get(guild_id)

    monkeypatch.setattr(Bot, "is_ready", is_ready)
    monkeypatch.setattr(Bot, "get_guild", get_guild)

    bot = await load_plugin("Ticket", tmp_path / "plugins", store)

    assert bot.loaded == ("Ticket",)
    assert await store.get(NAMESPACE, "11") is None
