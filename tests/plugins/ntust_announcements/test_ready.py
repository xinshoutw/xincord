"""The boards' channels, checked when the bot is ready.

v3 looked its guild up with ``!!`` when it started, which stopped the bot outside the owner's guild,
and each announcement channel when it first posted there.
"""

import logging
from typing import TYPE_CHECKING, cast

import payloads
from plugin_fakes import add_guild, dispatch, load_plugin
from xincord.core.bot import Bot

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from xincord.core.storage import Store
    from xincord.plugins.ntust_announcements.cog import NtustAnnouncements

LOGGER = "xincord.plugins.ntust_announcements"
CATEGORY = 4
FORUM = 15
VOICE = 2


def warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """The plugin's warnings."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith(LOGGER) and record.levelno == logging.WARNING
    ]


def cog_of(bot: Bot) -> NtustAnnouncements:
    """The loaded plugin's cog."""
    return cast("NtustAnnouncements", bot.get_cog("NtustAnnouncements"))


async def test_missing_channel(bot: Bot, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Channels are checked when the bot is ready."""
    add_guild(bot, payloads.guild(10, channels=[payloads.channel(101, "dormitory")]))

    await dispatch(bot, "ready")

    assert warnings(caplog) == [
        "NtustAnnouncements board LANGUAGE_CENTER_RECRUITMENT: the bot cannot see channel 102"
    ]


async def test_channel_without_messages(bot: Bot, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Channels are checked when the bot is ready."""
    channels = [
        payloads.channel(101, "announcements", kind=CATEGORY),
        payloads.channel(102, "language-center", kind=FORUM),
    ]
    add_guild(bot, payloads.guild(10, channels=channels))

    cog_of(bot).check()

    assert warnings(caplog) == [
        "NtustAnnouncements board STUDENT_DORMITORY: channel 101 takes no messages",
        "NtustAnnouncements board LANGUAGE_CENTER_RECRUITMENT: channel 102 takes no messages",
    ]


async def test_channels_that_take_messages(bot: Bot, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Channels are checked when the bot is ready."""
    channels = [payloads.channel(101, "dormitory"), payloads.channel(102, "lc", kind=VOICE)]
    add_guild(bot, payloads.guild(10, channels=channels))

    cog_of(bot).check()

    assert warnings(caplog) == []  # a text channel and a voice channel's chat


async def test_loaded_into_a_ready_bot(
    store: Store,
    tmp_path: Path,
    config: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: Channels are checked when the bot is ready."""

    def is_ready(_bot: Bot) -> bool:
        return True  # as after a reload; no guild is cached

    monkeypatch.setattr(Bot, "is_ready", is_ready)

    bot = await load_plugin("NtustAnnouncements", tmp_path / "plugins", store, config=config)

    assert bot.loaded == ("NtustAnnouncements",)
    assert warnings(caplog) == [
        "NtustAnnouncements board STUDENT_DORMITORY: the bot cannot see channel 101",
        "NtustAnnouncements board LANGUAGE_CENTER_RECRUITMENT: the bot cannot see channel 102",
    ]
