"""The AutoRole config.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/kotlin/autorole/config/ConfigSerializer.kt:6-24
    XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/kotlin/autorole/AutoRole.kt:9-12
    XsDiscordBotKt@3a59607:Plugins/AutoRole/src/main/resources/config.yaml:1-10
"""

import logging
from typing import TYPE_CHECKING

import pytest

from plugin_fakes import load_plugin
from xincord.plugins.auto_role.cog import AutoRole
from xincord.plugins.auto_role.config import Config

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store

# v3's shape with 64-bit IDs; the values are placeholders.
V3_CONFIG = """\
enabled: true
guilds:
  - guild_id: 111111111111111111
    role_ids:
      - 222222222222222222
      - 333333333333333333
"""


def loaded_cog(bot: Bot) -> AutoRole:
    """The cog of the loaded plugin."""
    cog = bot.get_cog("AutoRole")
    assert isinstance(cog, AutoRole)
    return cog


async def test_v3_config_file(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config lists guilds and their roles."""
    with caplog.at_level(logging.WARNING):
        bot = await load_plugin("AutoRole", tmp_path / "plugins", store, config=V3_CONFIG)

    assert loaded_cog(bot).roles == {111111111111111111: (222222222222222222, 333333333333333333)}
    assert "unknown key enabled" in caplog.text
    assert "unknown key guilds" not in caplog.text


async def test_default_config(tmp_path: Path, store: Store) -> None:
    """Requirement: The config lists guilds and their roles."""
    bot = await load_plugin("AutoRole", tmp_path / "plugins", store)

    assert loaded_cog(bot).roles == {}


@pytest.mark.parametrize(
    ("config", "error"),
    [
        ("enabled: true\n", "guilds: Field required"),
        (
            "guilds:\n  - guild_id: 0\n    role_ids: [1]\n",
            "guilds.0.guild_id: Input should be greater than 0",
        ),
        (
            "guilds:\n  - guild_id: 1\n    role_ids: []\n",
            "guilds.0.role_ids: Tuple should have at least 1 item",
        ),
    ],
)
async def test_invalid_entries(
    config: str, error: str, tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config lists guilds and their roles."""
    bot = await load_plugin("AutoRole", tmp_path / "plugins", store, config=config)

    assert bot.loaded == ()
    assert error in caplog.text


def test_guild_listed_twice() -> None:
    """Requirement: The config lists guilds and their roles."""
    config = Config.model_validate(
        {
            "guilds": [
                {"guild_id": 1, "role_ids": [2]},
                {"guild_id": 3, "role_ids": [4]},
                {"guild_id": 1, "role_ids": [5, 6]},
            ]
        }
    )

    assert config.roles_by_guild() == {1: (5, 6), 3: (4,)}
