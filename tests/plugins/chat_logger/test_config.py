"""The ChatLogger config: v3's ``log_all`` and the retention of the stored messages.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/config/ConfigSerializer.kt:6-11
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/resources/config.yaml:1-2
"""

import logging
from typing import TYPE_CHECKING, cast

import pytest

from plugin_fakes import load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.chat_logger.cog import ChatLogger
    from xincord.plugins.chat_logger.config import Config

V3_CONFIG = "enabled: false\nlog_all: false\n"  # v3's keys; its shipped file had log_all true


def loaded_config(bot: Bot) -> Config:
    """The config of the loaded plugin's cog.

    When a plugin's setup fails, as with the invalid files below, discord.py drops its modules, and
    the next load imports them again: an isinstance check against the class imported here would
    depend on the test order.
    """
    cog = bot.get_cog("ChatLogger")
    assert cog is not None
    return cast("ChatLogger", cog).config


def warned_keys(caplog: pytest.LogCaptureFixture) -> set[str]:
    """The keys that the config's unknown-key warnings name."""
    marker = "unknown key "
    return {message.split(marker)[-1] for message in caplog.messages if marker in message}


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The config keeps v3's key and bounds the stored messages",
)
async def test_v3_file(tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The config keeps v3's key and bounds the stored messages."""
    with caplog.at_level(logging.WARNING):
        bot = await load_plugin("ChatLogger", tmp_path / "plugins", store, config=V3_CONFIG)

    assert warned_keys(caplog) == {"enabled"}
    config = loaded_config(bot)
    assert config.log_all is False
    assert config.retention_days == 30


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The config keeps v3's key and bounds the stored messages",
)
async def test_bundled_file(tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The config keeps v3's key and bounds the stored messages."""
    with caplog.at_level(logging.WARNING):
        bot = await load_plugin("ChatLogger", tmp_path / "plugins", store)

    config = loaded_config(bot)
    assert config.log_all is True
    assert config.retention_days == 30
    assert warned_keys(caplog) == set()


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="The config keeps v3's key and bounds the stored messages",
)
@pytest.mark.parametrize("days", [1, 3650])
async def test_retention_range(days: int, tmp_path: Path, store: Store) -> None:
    """Requirement: The config keeps v3's key and bounds the stored messages."""
    config = f"retention_days: {days}\n"

    bot = await load_plugin("ChatLogger", tmp_path / "plugins", store, config=config)

    assert loaded_config(bot).retention_days == days


@pytest.mark.xfail(strict=True, reason="The config keeps v3's key and bounds the stored messages")
@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("retention_days: 0\n", "retention_days: Input should be greater than or equal to 1"),
        ("retention_days: 3651\n", "retention_days: Input should be less than or equal to 3650"),
        ("retention_days: x\n", "retention_days: Input should be a valid integer"),
    ],
    ids=["zero", "too-long", "text"],
)
async def test_invalid_retention(
    text: str, error: str, tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config keeps v3's key and bounds the stored messages."""
    bot = await load_plugin("ChatLogger", tmp_path / "plugins", store, config=text)

    assert bot.loaded == ()
    assert error in caplog.text


async def test_invalid_log_all(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config keeps v3's key and bounds the stored messages."""
    bot = await load_plugin("ChatLogger", tmp_path / "plugins", store, config="log_all: maybe\n")

    assert bot.loaded == ()
    assert "log_all: Input should be a valid boolean" in caplog.text
