"""Requirement: v3 core config migrates to the new schema.

Kotlin: XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/setting/SettingSerializer.kt,
Core/src/main/kotlin/core/builtin/statuschanger/StatusChanger.kt:72-90 and
Core/src/main/kotlin/core/builtin/consolelogger/ConsoleLogger.kt:40-60.
"""

from typing import TYPE_CHECKING, Any

import pytest

from xincord.core.config import CoreConfig, load_config
from xincord.core.migrate_v3 import (
    enabled_v3_plugins,
    main,
    migrate_core_config,
    migrate_directory,
)

if TYPE_CHECKING:
    from pathlib import Path


def v3(activities: list[str], loggers: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "general_settings": {"bot_token": "token-123"},
        "builtin_settings": {
            "status_changer_settings": {"activity_messages": activities},
            "console_logger_settings": loggers or [],
        },
    }


V3_TEXT = """\
general_settings:
  bot_token: "token-123"

builtin_settings:
  status_changer_settings:
    # PLAYING / STREAMING / LISTENING / WATCHING / CUSTOM_STATUS / COMPETING
    activity_messages:
      - "COMPETING;Developing...;5000"
"""


def test_v3_file_is_converted() -> None:
    target = {"guild_id": 1, "channel_id": 2, "log_type": ["command", "modal"], "format": "[x]"}

    new, report = migrate_core_config(
        v3(["COMPETING;Developing...;5000", "CUSTOM_STATUS;Hello;2500"], [target]),
    )

    assert report == []
    assert new == {
        "token": "token-123",
        "status": {
            "activities": [
                {"type": "competing", "text": "Developing...", "seconds": 5.0},
                {"type": "custom", "text": "Hello", "seconds": 2.5},
            ],
        },
        "interaction_log": [
            {"guild_id": 1, "channel_id": 2, "types": ["command", "modal"], "format": "[x]"},
        ],
    }
    CoreConfig.model_validate(new)


def test_streaming_activity_keeps_its_url() -> None:
    new, _ = migrate_core_config(
        v3(["STREAMING;Live;https://twitch.tv/example", "STREAMING;Late;https://e.com/l;8000"]),
    )

    assert new["status"] == {
        "activities": [
            {"type": "streaming", "text": "Live", "url": "https://twitch.tv/example"},
            {"type": "streaming", "text": "Late", "url": "https://e.com/l", "seconds": 8.0},
        ],
    }
    assert CoreConfig.model_validate(new).status.activities[0].seconds == 5


@pytest.mark.parametrize(
    "entry",
    ["PLAYING;only two", "DANCING;x;100", "PLAYING;x;soon", "PLAYING;x;0", "STREAMING;x;"],
)
def test_unconvertible_activities_are_reported(entry: str) -> None:
    new, report = migrate_core_config(v3([entry]))

    assert new["status"] == {"activities": []}
    assert len(report) == 1
    assert entry in report[0]


def test_unknown_log_types_are_reported() -> None:
    mixed = {"guild_id": 1, "channel_id": 2, "log_type": ["command", "select"], "format": "x"}
    unknown = {"guild_id": 3, "channel_id": 4, "log_type": ["select"], "format": "x"}

    new, report = migrate_core_config(v3([], [mixed, unknown]))

    assert new["interaction_log"] == [
        {"guild_id": 1, "channel_id": 2, "types": ["command"], "format": "x"},
    ]
    assert len(report) == 2
    assert all("select" in line for line in report)


def test_original_file_is_backed_up(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(V3_TEXT, encoding="utf-8")

    report = migrate_directory(tmp_path)

    assert (tmp_path / "config.v3.yaml").read_text(encoding="utf-8") == V3_TEXT
    config = load_config(tmp_path / "config.yaml", CoreConfig, "")
    assert config.token == "token-123"
    assert config.status.activities[0].text == "Developing..."
    assert "config.v3.yaml" in report[-1]


def test_migrated_file_is_left_alone(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("token: abc\n", encoding="utf-8")

    report = migrate_directory(tmp_path)

    assert (tmp_path / "config.yaml").read_text(encoding="utf-8") == "token: abc\n"
    assert not (tmp_path / "config.v3.yaml").exists()
    assert len(report) == 1


def test_existing_backup_blocks_migration(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(V3_TEXT, encoding="utf-8")
    (tmp_path / "config.v3.yaml").write_text("older", encoding="utf-8")

    report = migrate_directory(tmp_path)

    assert (tmp_path / "config.yaml").read_text(encoding="utf-8") == V3_TEXT
    assert (tmp_path / "config.v3.yaml").read_text(encoding="utf-8") == "older"
    assert len(report) == 1


def test_command_line_prints_the_report(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "config.yaml").write_text(V3_TEXT, encoding="utf-8")

    assert main([str(tmp_path)]) == 0
    assert "config.v3.yaml" in capsys.readouterr().out


def test_missing_token_and_file_are_reported(tmp_path: Path) -> None:
    new, report = migrate_core_config({"general_settings": {}})

    assert new["token"] == ""
    assert report == ["general_settings.bot_token: missing, token left empty"]
    assert migrate_directory(tmp_path) == [f"{tmp_path / 'config.yaml'}: not found"]


def test_enabled_v3_plugins(tmp_path: Path) -> None:
    """Requirement: v3 plugin switches migrate to the enabled list."""
    (tmp_path / "config.yaml").write_text(V3_TEXT, encoding="utf-8")
    for name, text in (
        ("Ticket", "enabled: false\n"),
        ("AutoRole", "enabled: true\nguild_id: 1\n"),
    ):
        (tmp_path / "plugins" / name).mkdir(parents=True)
        (tmp_path / "plugins" / name / "config.yaml").write_text(text, encoding="utf-8")
    (tmp_path / "plugins" / "SQLiteAPI").mkdir()

    assert enabled_v3_plugins(tmp_path) == ["AutoRole"]
    report = migrate_directory(tmp_path)

    assert load_config(tmp_path / "config.yaml", CoreConfig, "").plugins == ("AutoRole",)
    assert any("AutoRole" in line for line in report)


# Decision B18 as amended on 2026-10-10 (docs/porting/decisions.md): v3 names and their new
# names, sorted by the new name.
RENAMED = (
    ("BasicCalculator", "Calculator"),
    ("SimpleCommand", "CustomCommands"),
    ("_Example", "Example"),
    ("Feedbacker", "Feedback"),
    ("NtustManager", "NtustAnnouncements"),
    ("NtustCourse", "NtustCourseWatch"),
    ("TicketAddons", "TicketAwayNotice"),
    ("IntervalPusher", "UptimeHeartbeat"),
    ("WelcomeByeGuild", "WelcomeGoodbye"),
)


def write_plugin(root: Path, name: str, text: str) -> Path:
    """Write ``root/plugins/<name>/config.yaml`` and return the plugin's directory."""
    directory = root / "plugins" / name
    directory.mkdir(parents=True)
    (directory / "config.yaml").write_text(text, encoding="utf-8")
    return directory


def test_renamed_v3_plugins(tmp_path: Path) -> None:
    """Requirement: v3 plugin switches migrate to the enabled list."""
    (tmp_path / "config.yaml").write_text(V3_TEXT, encoding="utf-8")
    for old, _ in RENAMED:
        write_plugin(tmp_path, old, "enabled: true\n")
    names = [new for _, new in RENAMED]

    assert enabled_v3_plugins(tmp_path) == names
    report = migrate_directory(tmp_path)

    assert load_config(tmp_path / "config.yaml", CoreConfig, "").plugins == tuple(names)
    assert f"plugins: enabled {', '.join(names)}" in report


def test_renamed_directory_moves(tmp_path: Path) -> None:
    """Requirement: Renamed plugins' v3 directories move to their new names."""
    (tmp_path / "config.yaml").write_text(V3_TEXT, encoding="utf-8")
    text = "enabled: false\nform_success: done\n"
    old = write_plugin(tmp_path, "Feedbacker", text)
    (old / "lang" / "zh-TW").mkdir(parents=True)
    write_plugin(tmp_path, "AutoRole", "enabled: true\n")

    report = migrate_directory(tmp_path)

    new = tmp_path / "plugins" / "Feedback"
    assert (new / "config.yaml").read_text(encoding="utf-8") == text
    assert (new / "lang" / "zh-TW").is_dir()
    assert not old.exists()
    assert (tmp_path / "plugins" / "AutoRole" / "config.yaml").is_file()
    assert f"{old}: moved to {new}" in report


def test_existing_new_directory_is_kept(tmp_path: Path) -> None:
    """Requirement: Renamed plugins' v3 directories move to their new names."""
    (tmp_path / "config.yaml").write_text(V3_TEXT, encoding="utf-8")
    old = write_plugin(tmp_path, "Feedbacker", "enabled: true\n")
    new = write_plugin(tmp_path, "Feedback", "form_success: newer\n")

    report = migrate_directory(tmp_path)

    assert (old / "config.yaml").read_text(encoding="utf-8") == "enabled: true\n"
    assert (new / "config.yaml").read_text(encoding="utf-8") == "form_success: newer\n"
    assert f"{old}: kept, {new} exists" in report
    assert load_config(tmp_path / "config.yaml", CoreConfig, "").plugins == ("Feedback",)


def test_migrated_directory_is_left_alone(tmp_path: Path) -> None:
    """Requirement: Renamed plugins' v3 directories move to their new names."""
    (tmp_path / "config.yaml").write_text(V3_TEXT, encoding="utf-8")
    write_plugin(tmp_path, "BasicCalculator", "enabled: true\n")
    migrate_directory(tmp_path)
    assert (tmp_path / "plugins" / "Calculator" / "config.yaml").is_file()

    old = write_plugin(tmp_path, "Feedbacker", "enabled: true\n")
    migrated = migrate_directory(tmp_path)  # config.yaml is in the new schema now
    (tmp_path / "config.yaml").write_text(V3_TEXT, encoding="utf-8")
    backed_up = migrate_directory(tmp_path)  # config.v3.yaml exists

    assert (old / "config.yaml").is_file()
    assert not (tmp_path / "plugins" / "Feedback").exists()
    assert len(migrated) == len(backed_up) == 1
