"""The TicketAwayNotice config: v3's keys, without defaults, validated when the plugin loads.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/config/ConfigSerializer.kt:6-26
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/resources/config.yaml:1-7
"""

import logging
from typing import TYPE_CHECKING

import pytest

from plugin_fakes import golden, load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.storage import Store

GOLDEN = golden("ticket_away_notice")
VALID = """\
guild_id: 10
user_id: 20
prefix: ["ticket-"]
delay_millis: 2000
"""


@pytest.mark.parametrize("quoting", ["unquoted", "quoted"])
async def test_v3_config_file(
    quoting: str, tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config names the guild, the owner, the prefixes and the delay."""
    config = GOLDEN["v3_config"][quoting]

    with caplog.at_level(logging.WARNING):
        bot = await load_plugin("TicketAwayNotice", tmp_path / "plugins", store, config=config)

    assert bot.loaded == ("TicketAwayNotice",)
    assert "unknown key enabled" in caplog.text
    for key in ("guild_id", "user_id", "prefix", "delay_millis"):
        assert f"unknown key {key}" not in caplog.text


async def test_bundled_config(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config names the guild, the owner, the prefixes and the delay."""
    bot = await load_plugin("TicketAwayNotice", tmp_path / "plugins", store)

    assert bot.loaded == ()
    assert "guild_id: Input should be greater than 0" in caplog.text
    assert "user_id: Input should be greater than 0" in caplog.text


@pytest.mark.parametrize(
    ("change", "error"),
    [
        (('prefix: ["ticket-"]', "prefix: []"), "prefix: Tuple should have at least 1 item"),
        (
            ("delay_millis: 2000", "delay_millis: 0"),
            "delay_millis: Input should be greater than or equal to 1",
        ),
        (
            # v3's Long held no more.
            ("delay_millis: 2000", "delay_millis: 9223372036854775808"),
            "delay_millis: Input should be less than or equal to 9223372036854775807",
        ),
        (("user_id: 20", "user_id: owner"), "user_id: Input should be a valid integer"),
        (("guild_id: 10", "guild_id: -10"), "guild_id: Input should be greater than 0"),
    ],
)
async def test_invalid_values(
    change: tuple[str, str],
    error: str,
    tmp_path: Path,
    store: Store,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: The config names the guild, the owner, the prefixes and the delay."""
    config = VALID.replace(*change)
    assert config != VALID

    bot = await load_plugin("TicketAwayNotice", tmp_path / "plugins", store, config=config)

    assert bot.loaded == ()
    assert error in caplog.text
