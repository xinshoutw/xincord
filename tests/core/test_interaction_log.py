"""The interaction log.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-65
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/consolelogger/ConsoleLogger.kt:91-139
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import discord
import pytest

from plugin_fakes import write_config
from xincord.core.bot import Bot
from xincord.core.config import CoreConfig, InteractionLogTarget
from xincord.core.interaction_log import describe

if TYPE_CHECKING:
    from collections.abc import Mapping

    from aiohttp import ClientResponse

    from xincord.core.storage import Store

COMMAND = discord.InteractionType.application_command
COMPONENT = discord.InteractionType.component
MODAL = discord.InteractionType.modal_submit
AUTOCOMPLETE = discord.InteractionType.autocomplete
PING: dict[str, object] = {"type": 1, "name": "ping"}
BUTTON: dict[str, object] = {"component_type": 2, "custom_id": "b"}
SUBMIT: dict[str, object] = {"custom_id": "m", "components": []}


@dataclass(frozen=True)
class Asset:
    url: str


@dataclass(frozen=True)
class User:
    id: int = 1
    name: str = "alice"
    global_name: str | None = None
    avatar: Asset | None = None
    default_avatar: Asset = Asset("https://cdn.example/default.png")
    bot: bool = False
    created_at: datetime = datetime(2021, 6, 1, tzinfo=UTC)

    @property
    def mention(self) -> str:
        return f"<@{self.id}>"


@dataclass
class FakeInteraction:
    type: discord.InteractionType
    data: Mapping[str, object]
    user: User = field(default_factory=User)
    locale: discord.Locale = discord.Locale.american_english
    channel: object = None
    message: object = None


def interaction(kind: discord.InteractionType, data: Mapping[str, object]) -> discord.Interaction:
    return cast("discord.Interaction", FakeInteraction(kind, data))


@pytest.mark.parametrize(
    ("kind", "data", "expected"),
    [
        (
            COMMAND,
            {"type": 1, "name": "ping", "options": [{"type": 4, "name": "count", "value": 2}]},
            ("CMD", "/ping count: 2"),
        ),
        (COMMAND, {"type": 3, "name": "Report", "target_id": "5"}, ("MSG", "Report")),
        (COMPONENT, BUTTON, ("BTN", "b")),
        (COMPONENT, {"component_type": 3, "custom_id": "s", "values": ["x"]}, ("STRING", "s")),
        (COMPONENT, {"component_type": 5, "custom_id": "u", "values": ["1"]}, ("ENTITY", "u")),
        (MODAL, SUBMIT, ("MODAL", "m")),
        (AUTOCOMPLETE, PING, None),
        (COMMAND, {"type": 2, "name": "Inspect", "target_id": "5"}, None),
    ],
)
def test_describe(
    kind: discord.InteractionType, data: Mapping[str, object], expected: tuple[str, str] | None
) -> None:
    """Requirement: Interaction console lines."""
    assert describe(interaction(kind, data)) == expected


async def test_console_lines(
    store: Store, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Interaction console lines."""
    caplog.set_level(logging.INFO)
    bot = Bot([], root=tmp_path, data=tmp_path / "data", store=store)

    await bot.on_interaction(interaction(COMMAND, PING))
    await bot.on_interaction(interaction(COMPONENT, BUTTON))

    assert "[CMD] alice: /ping" in caplog.text
    assert "[BTN] alice: b" in caplog.text


class Channels:
    """Fake log channels; the IDs in ``failing`` reject every message."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, *failing: int) -> None:
        self.sent: dict[int, list[str]] = {}
        self.mentions: list[object] = []
        self.guilds: set[int | None] = set()
        self.failing = failing
        monkeypatch.setattr(Bot, "get_partial_messageable", self.get)
        monkeypatch.setattr(Bot, "user", property(lambda _: User(id=99, name="xincord")))

    def get(self, channel_id: int, *, guild_id: int | None = None) -> object:
        self.guilds.add(guild_id)

        async def send(content: str, *, allowed_mentions: discord.AllowedMentions) -> None:
            if channel_id in self.failing:
                response = cast("ClientResponse", SimpleNamespace(status=403, reason="Forbidden"))
                raise discord.Forbidden(response, "Missing Access")
            self.sent.setdefault(channel_id, []).append(content)
            self.mentions.append(allowed_mentions.to_dict())

        return SimpleNamespace(send=send)


def target(channel_id: int, *types: str, text: str | None = None) -> InteractionLogTarget:
    extra = {} if text is None else {"format": text}
    return InteractionLogTarget.model_validate(
        {"guild_id": 1, "channel_id": channel_id, "types": types, **extra}
    )


async def test_matching_targets(
    store: Store, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement: Interaction log channels."""
    config = CoreConfig(interaction_log=(target(10, "command", "modal"), target(20, "button")))
    bot = Bot([], root=tmp_path, data=tmp_path / "data", store=store, config=config)
    channels = Channels(monkeypatch)

    await bot.on_interaction(interaction(COMMAND, PING))
    await bot.on_interaction(interaction(COMPONENT, BUTTON))
    await bot.on_interaction(interaction(MODAL, SUBMIT))

    assert channels.sent == {
        10: ["[CMD] alice `/ping`", "[MODAL] alice `m`"],
        20: ["[BTN] alice `b`"],
    }
    assert channels.guilds == {1}


@pytest.mark.usefixtures("installed")
async def test_no_pings_failures_and_reload(
    store: Store, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Interaction log channels."""
    mention = "%user_mention% used %cl_interaction_string% as %cl_type%"
    config = CoreConfig(interaction_log=(target(10, "button"), target(20, "button", text=mention)))
    bot = Bot([], root=Path("plugins"), data=Path("data"), store=store, config=config)
    channels = Channels(monkeypatch, 10)

    await bot.on_interaction(interaction(COMPONENT, BUTTON))
    write_config(
        "interaction_log:\n"
        "  - {guild_id: 1, channel_id: 20, types: [button], format: '%user_name%'}\n"
        "  - {guild_id: 1, channel_id: 30, types: [button]}\n"
    )
    assert await bot.reload() == "Reloaded: none."
    await bot.on_interaction(interaction(COMPONENT, BUTTON))

    assert channels.sent == {20: ["<@1> used b as BTN", "alice"], 30: ["[BTN] alice `b`"]}
    assert channels.mentions == [{"parse": []}] * 3
    assert "10" in caplog.text
