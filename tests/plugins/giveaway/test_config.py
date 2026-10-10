"""The Giveaway config: v3's ``defaultLocale`` and ``autoDrawIntervalSeconds``, and ``timeZone``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/config/ConfigSerializer.kt:5-10
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/resources/config.yaml:1-7
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Event.kt:22-46
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:93-113
"""

import logging
from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

import pytest

from plugin_fakes import load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.giveaway.cog import Giveaway
    from xincord.plugins.giveaway.config import Config

# v3's bundled config.yaml.
V3_CONFIG = """enabled: false
# default locale fallback for message/modal resources
defaultLocale: "zh-TW"

# Interval (in seconds) for auto-draw polling.
# Lower values increase server load when there are many guilds/giveaways.
autoDrawIntervalSeconds: 60
"""


def loaded(bot: Bot) -> Giveaway:
    """The loaded plugin's cog.

    When a plugin's setup fails, as with the invalid files below, discord.py drops its modules, and
    the next load imports them again: an isinstance check against the class imported here would
    depend on the test order.
    """
    cog = bot.get_cog("Giveaway")
    assert cog is not None
    return cast("Giveaway", cog)


def loaded_config(bot: Bot) -> Config:
    """The config of the loaded plugin's cog."""
    return loaded(bot).config


def warned_keys(caplog: pytest.LogCaptureFixture) -> set[str]:
    """The keys that the config's unknown-key warnings name."""
    marker = "unknown key "
    return {message.split(marker)[-1] for message in caplog.messages if marker in message}


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="The config keeps v3's keys")
async def test_v3_file(tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The config keeps v3's keys."""
    with caplog.at_level(logging.WARNING):
        bot = await load_plugin("Giveaway", tmp_path / "plugins", store, config=V3_CONFIG)

    config = loaded_config(bot)
    assert config.default_locale == "zh-TW"
    assert config.period == 60
    assert config.zone is None  # the host's zone, as v3's ZoneId.systemDefault()
    assert warned_keys(caplog) == {"enabled"}


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="The config keeps v3's keys")
async def test_bundled_file(tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The config keeps v3's keys."""
    with caplog.at_level(logging.WARNING):
        bot = await load_plugin("Giveaway", tmp_path / "plugins", store)

    config = loaded_config(bot)
    assert config.default_locale == "zh-TW"
    assert config.period == 60
    assert config.zone is None
    assert warned_keys(caplog) == set()


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="The config keeps v3's keys")
@pytest.mark.parametrize(
    ("seconds", "period"),
    [(1, 5), (0, 5), (-5, 5), (5, 5), (300, 300), (3600, 3600), (99999, 3600)],
)
async def test_clamped_interval(seconds: int, period: int, tmp_path: Path, store: Store) -> None:
    """Requirement: The config keeps v3's keys."""
    text = f"autoDrawIntervalSeconds: {seconds}\n"

    bot = await load_plugin("Giveaway", tmp_path / "plugins", store, config=text)

    assert loaded_config(bot).period == period  # v3's coerceIn(5, 3600)


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="The config keeps v3's keys")
async def test_time_zone(tmp_path: Path, store: Store) -> None:
    """Requirement: The config keeps v3's keys."""
    text = 'timeZone: "Asia/Taipei"\n'

    bot = await load_plugin("Giveaway", tmp_path / "plugins", store, config=text)

    assert loaded_config(bot).zone == ZoneInfo("Asia/Taipei")


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="The config keeps v3's keys")
async def test_other_default_locale(tmp_path: Path, store: Store) -> None:
    """Requirement: The config keeps v3's keys."""
    text = 'defaultLocale: "en-US"\n'

    bot = await load_plugin("Giveaway", tmp_path / "plugins", store, config=text)

    assert loaded_config(bot).default_locale == "en-US"
    assert loaded(bot).lang.default_locale == "en-US"


@pytest.mark.xfail(strict=True, reason="The config keeps v3's keys")
@pytest.mark.parametrize(
    ("text", "error"),
    [
        ('defaultLocale: "zh-tw"\n', "defaultLocale: Value error, zh-tw is not a Discord locale"),
        ("defaultLocale: 5\n", "defaultLocale: Input should be a valid string"),
        ('timeZone: "Mars/Base"\n', "timeZone: Value error, Mars/Base is not a time zone"),
        ('timeZone: "../etc"\n', "timeZone: Value error, ../etc is not a time zone"),
        ("autoDrawIntervalSeconds: soon\n", "autoDrawIntervalSeconds: Input should be a valid"),
        ("autoDrawIntervalSeconds: 1.5\n", "autoDrawIntervalSeconds: Input should be a valid"),
    ],
    ids=["locale-case", "locale-number", "zone", "zone-path", "interval-text", "interval-float"],
)
async def test_invalid_values(
    text: str, error: str, tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config keeps v3's keys."""
    bot = await load_plugin("Giveaway", tmp_path / "plugins", store, config=text)

    assert bot.loaded == ()
    assert error in caplog.text


@pytest.mark.xfail(strict=True, reason="The config keeps v3's keys")
async def test_locale_without_lang_files(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config keeps v3's keys."""
    text = 'defaultLocale: "ja"\n'  # a Discord locale, but the plugin has no ja files

    bot = await load_plugin("Giveaway", tmp_path / "plugins", store, config=text)

    assert bot.loaded == ()
    assert "Giveaway: no lang directory for the default locale ja" in caplog.text
