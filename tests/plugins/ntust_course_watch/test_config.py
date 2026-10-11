"""The NtustCourseWatch config: what v3 hard-coded, with v3's values as defaults.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/config/ConfigSerializer.kt:5-8
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/api/CourseMonitorService.kt:22-36
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/NtustCourse.kt:97-100
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, cast

import pytest

from plugin_fakes import load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.ntust_course_watch.cog import NtustCourseWatch
    from xincord.plugins.ntust_course_watch.config import Config

TAIWAN = timezone(timedelta(hours=8))
V3_START = datetime(2025, 12, 26, 9, 0, tzinfo=TAIWAN)  # v3's go-live time on the owner's host
VALID = """\
semester: "1151"
start: 2026-12-28T09:00:00+08:00
interval: 1.5
alert-interval: 60
"""


def config_of(bot: Bot) -> Config:
    """The loaded plugin's config."""
    return cast("NtustCourseWatch", bot.get_cog("NtustCourseWatch")).config


async def test_v3_config_file(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config names the semester, the start and the intervals."""
    with caplog.at_level(logging.WARNING):
        bot = await load_plugin(
            "NtustCourseWatch", tmp_path / "plugins", store, config="enabled: false"
        )

    assert bot.loaded == ("NtustCourseWatch",)
    assert "unknown key enabled" in caplog.text
    config = config_of(bot)
    assert config.semester == "1142"  # v3's hard-coded semester
    assert config.start == V3_START
    assert config.interval == 1.5  # v3's target cadence
    assert config.alert_interval == 60


async def test_bundled_config(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config names the semester, the start and the intervals."""
    with caplog.at_level(logging.WARNING):
        bot = await load_plugin("NtustCourseWatch", tmp_path / "plugins", store)

    assert bot.loaded == ("NtustCourseWatch",)
    assert "unknown key" not in caplog.text
    config = config_of(bot)
    assert (config.semester, config.start, config.interval, config.alert_interval) == (
        "1142",
        V3_START,
        1.5,
        60,
    )


@pytest.mark.parametrize(
    ("line", "semester"),
    [
        pytest.param("semester: 1151", "1151", id="number"),
        pytest.param("semester: 114H", "114H", id="summer term"),
        pytest.param('semester: "1151"', "1151", id="quoted"),
    ],
)
async def test_numbers_as_text(tmp_path: Path, store: Store, line: str, semester: str) -> None:
    """Requirement: The config names the semester, the start and the intervals."""
    text = VALID.replace('semester: "1151"', line)

    bot = await load_plugin("NtustCourseWatch", tmp_path / "plugins", store, config=text)

    assert config_of(bot).semester == semester


async def test_valid_values(tmp_path: Path, store: Store) -> None:
    """Requirement: The config names the semester, the start and the intervals."""
    text = VALID.replace("interval: 1.5", "interval: 1").replace(
        "alert-interval: 60", "alert-interval: 10"
    )

    bot = await load_plugin("NtustCourseWatch", tmp_path / "plugins", store, config=text)

    config = config_of(bot)
    assert config.start == datetime(2026, 12, 28, 9, 0, tzinfo=TAIWAN)
    assert (config.interval, config.alert_interval) == (1, 10)  # the minimums


@pytest.mark.parametrize(
    ("change", "error"),
    [
        pytest.param(
            ('semester: "1151"', 'semester: "11 51"'),
            "semester: String should match pattern",
            id="semester with a space",
        ),
        pytest.param(
            ('semester: "1151"', 'semester: ""'),
            "semester: String should match pattern",
            id="empty semester",
        ),
        pytest.param(
            ("start: 2026-12-28T09:00:00+08:00", "start: 2026-12-28T09:00:00"),
            "start: Input should have timezone info",
            id="start without offset",
        ),
        pytest.param(
            ("start: 2026-12-28T09:00:00+08:00", 'start: "tomorrow"'),
            "start: Input should be a valid datetime",
            id="start not a time",
        ),
        pytest.param(
            ("interval: 1.5", "interval: 0.5"),
            "interval: Input should be greater than or equal to 1",
            id="interval below 1",
        ),
        pytest.param(
            ("interval: 1.5", "interval: .inf"),
            "interval: Input should be a finite number",
            id="interval infinite",
        ),
        pytest.param(
            ("interval: 1.5", "interval: 86401"),
            "interval: Input should be less than or equal to 86400",
            id="interval over a day",
        ),
        pytest.param(
            ("alert-interval: 60", "alert-interval: 5"),
            "alert-interval: Input should be greater than or equal to 10",
            id="alert interval below 10",
        ),
    ],
)
async def test_invalid_values(
    tmp_path: Path,
    store: Store,
    caplog: pytest.LogCaptureFixture,
    change: tuple[str, str],
    error: str,
) -> None:
    """Requirement: The config names the semester, the start and the intervals."""
    text = VALID.replace(*change)
    assert text != VALID

    bot = await load_plugin("NtustCourseWatch", tmp_path / "plugins", store, config=text)

    assert bot.loaded == ()
    assert error in caplog.text
