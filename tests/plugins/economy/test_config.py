"""The Economy config: the administrators and the length of the boards.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/config/ConfigSerializer.kt:6-42
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/resources/config.yaml:1-42
"""

import logging
from typing import TYPE_CHECKING, cast

import pytest

from plugin_fakes import golden, load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.economy.cog import Economy
    from xincord.plugins.economy.config import Config

GOLDEN = golden("economy")
# v3's keys for the dead Google Sheets storage, which only warn now.
SHEETS_KEYS = (
    "client_id",
    "client_secret",
    "port",
    "sheet_id",
    "sheet_label",
    "sheet_range_id",
    "sheet_range_money",
    "sheet_range_cost",
)


def loaded_config(bot: Bot) -> Config:
    """The config of the loaded plugin's cog.

    When a plugin's setup fails, as with the invalid files below, discord.py drops its modules, and
    the next load imports them again: an isinstance check against the class imported here would
    depend on the test order.
    """
    cog = bot.get_cog("Economy")
    assert cog is not None
    return cast("Economy", cog).config


def warned_keys(caplog: pytest.LogCaptureFixture) -> set[str]:
    """The keys that the config's unknown-key warnings name."""
    marker = "unknown key "
    return {message.split(marker)[-1] for message in caplog.messages if marker in message}


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="The config lists the administrators"
)
async def test_v3_file(tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The config lists the administrators."""
    with caplog.at_level(logging.WARNING):
        bot = await load_plugin("Economy", tmp_path / "plugins", store, config=GOLDEN["v3_config"])

    config = loaded_config(bot)
    assert config.admin_id == (111111111111111111, 222222222222222222)
    assert config.board_user_show_limit == 10
    assert warned_keys(caplog) == {"enabled", *SHEETS_KEYS}


@pytest.mark.xfail(strict=True, reason="The config lists the administrators")
async def test_bundled_file(tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The config lists the administrators."""
    bot = await load_plugin("Economy", tmp_path / "plugins", store)

    assert bot.loaded == ()
    assert "admin_id: Tuple should have at least 1 item after validation, not 0" in caplog.text


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="The config lists the administrators"
)
async def test_default_limit(tmp_path: Path, store: Store) -> None:
    """Requirement: The config lists the administrators."""
    bot = await load_plugin("Economy", tmp_path / "plugins", store, config="admin_id: [7]\n")

    config = loaded_config(bot)
    assert config.admin_id == (7,)
    assert config.board_user_show_limit == 10


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="The config lists the administrators"
)
@pytest.mark.parametrize("limit", [1, 25])
async def test_limit_range(limit: int, tmp_path: Path, store: Store) -> None:
    """Requirement: The config lists the administrators."""
    config = f"admin_id: [7]\nboard_user_show_limit: {limit}\n"

    bot = await load_plugin("Economy", tmp_path / "plugins", store, config=config)

    assert loaded_config(bot).board_user_show_limit == limit


@pytest.mark.xfail(strict=True, reason="The config lists the administrators")
@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("board_user_show_limit: 10\n", "admin_id: Field required"),
        ("admin_id: []\n", "admin_id: Tuple should have at least 1 item"),
        ("admin_id: [x]\n", "admin_id.0: Input should be a valid integer"),
        (
            "admin_id: [7]\nboard_user_show_limit: 0\n",
            "board_user_show_limit: Input should be greater than or equal to 1",
        ),
        (
            "admin_id: [7]\nboard_user_show_limit: 26\n",
            "board_user_show_limit: Input should be less than or equal to 25",
        ),
    ],
    ids=["no-admins", "empty-admins", "bad-admin", "limit-0", "limit-26"],
)
async def test_invalid_values(
    text: str, error: str, tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config lists the administrators."""
    bot = await load_plugin("Economy", tmp_path / "plugins", store, config=text)

    assert bot.loaded == ()
    assert error in caplog.text
