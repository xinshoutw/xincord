"""The UptimeHeartbeat config.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/config/ConfigSerializer.kt:5-15
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:61-123
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/resources/config.yaml:1-4
"""

import logging
from typing import TYPE_CHECKING, cast

import pytest

from plugin_fakes import load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.uptime_heartbeat.cog import UptimeHeartbeat

# v3's shipped listener, with an example domain instead of the owner's status domain.
PUSH_URL = "https://status.example.com/api/push/xxxxxxxxxx?status=up&msg=OK&ping=%ping%"
V3_CONFIG = f"""\
enabled: true
listeners:
  - url: "{PUSH_URL}"
    interval: 60
"""


def loaded_cog(bot: Bot) -> UptimeHeartbeat:
    """The cog of the loaded plugin.

    When a plugin's setup fails, as with the invalid files below, discord.py drops its modules, and
    the next load imports them again: an isinstance check against the class imported here would
    depend on the test order.
    """
    cog = bot.get_cog("UptimeHeartbeat")
    assert cog is not None
    return cast("UptimeHeartbeat", cog)


def listener(url: str = PUSH_URL, interval: str = "60") -> str:
    """A config file with one listener; ``url`` is written in double quotes."""
    return f'listeners:\n  - url: "{url}"\n    interval: {interval}\n'


async def test_v3_config_file(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config lists the URLs to push."""
    with caplog.at_level(logging.WARNING):
        bot = await load_plugin("UptimeHeartbeat", tmp_path / "plugins", store, config=V3_CONFIG)

    listeners = loaded_cog(bot).listeners
    assert [(entry.url, entry.interval) for entry in listeners] == [(PUSH_URL, 60)]
    assert "unknown key enabled" in caplog.text
    assert "unknown key listeners" not in caplog.text


async def test_default_config(tmp_path: Path, store: Store) -> None:
    """Requirement: The config lists the URLs to push."""
    bot = await load_plugin("UptimeHeartbeat", tmp_path / "plugins", store)

    assert loaded_cog(bot).listeners == ()


@pytest.mark.parametrize(
    ("config", "error"),
    [
        pytest.param("enabled: true\n", "listeners: Field required", id="no listeners"),
        pytest.param(
            listener(interval="0"),
            "listeners.0.interval: Input should be greater than or equal to 1",
            id="interval 0",
        ),
        pytest.param(
            listener(interval="-5"),
            "listeners.0.interval: Input should be greater than or equal to 1",
            id="negative interval",
        ),
        pytest.param(
            listener(interval="2147483648"),
            "listeners.0.interval: Input should be less than or equal to 2147483647",
            id="interval above v3's Int",
        ),
        pytest.param(
            listener("ftp://status.example.com/api/push/x"), "listeners.0.url: ", id="ftp"
        ),
        pytest.param(
            listener("status.example.com/api/push/x?ping=%ping%"),
            "listeners.0.url: ",
            id="no scheme",
        ),
        pytest.param(listener("https:///api/push/x"), "listeners.0.url: ", id="no host"),
        pytest.param(
            listener("https://status.example.com/api/push/x y"), "listeners.0.url: ", id="space"
        ),
        pytest.param(
            listener("https://status.example.com:99999/api/push/x"),
            "listeners.0.url: ",
            id="port out of range",
        ),
        pytest.param(listener("https://[::1/api/push/x"), "listeners.0.url: ", id="bad IPv6"),
    ],
)
async def test_invalid_entries(
    config: str, error: str, tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config lists the URLs to push."""
    bot = await load_plugin("UptimeHeartbeat", tmp_path / "plugins", store, config=config)

    assert bot.loaded == ()
    assert error in caplog.text


@pytest.mark.parametrize(
    "url",
    [
        PUSH_URL,
        "http://127.0.0.1:3001/api/push/x?status=up&msg=OK&ping=%ping%",
        "HTTPS://[::1]:3001/api/push/x",
        "https://status.example.com/%ping%/push?ping=%ping%",
    ],
)
async def test_accepted_urls(url: str, tmp_path: Path, store: Store) -> None:
    """Requirement: The config lists the URLs to push."""
    bot = await load_plugin("UptimeHeartbeat", tmp_path / "plugins", store, config=listener(url))

    assert [entry.url for entry in loaded_cog(bot).listeners] == [url]
