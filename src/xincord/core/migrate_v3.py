"""Migrate a v3 (XsDiscordBotKt) directory: the core ``config.yaml`` and the plugins' names.

Plugins whose config replaces what v3 kept in code (CustomCommands) get their v3 file set aside.

Run ``python -m xincord.core.migrate_v3 <server directory>`` once per installation.
"""

import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

import yaml

from xincord.core.config import CoreConfig

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

ACTIVITY_TYPES = {
    "PLAYING": "playing",
    "STREAMING": "streaming",
    "LISTENING": "listening",
    "WATCHING": "watching",
    "CUSTOM_STATUS": "custom",
    "COMPETING": "competing",
}
LOG_TYPES = ("command", "button", "modal")
# Plugins whose xincord name differs from v3's (decision B18 as amended on 2026-10-10). v3 kept
# each plugin's files in plugins/<v3 name>/:
RENAMED = {
    "_Example": "Example",
    "BasicCalculator": "Calculator",
    "SimpleCommand": "CustomCommands",
    "WelcomeByeGuild": "WelcomeGoodbye",
    "IntervalPusher": "UptimeHeartbeat",
    "Feedbacker": "Feedback",
    "TicketAddons": "TicketAwayNotice",
    "NtustManager": "NtustAnnouncements",
    "NtustCourse": "NtustCourseWatch",
}


# Plugins whose v3 config.yaml held only `enabled`, which the core config's plugins list carries
# now, and whose xincord config.yaml holds what v3 kept in its code (CustomCommands' commands).
SET_ASIDE = ("CustomCommands",)


def migrate_core_config(v3: Mapping[str, object]) -> tuple[dict[str, object], list[str]]:
    """Convert a parsed v3 core config to the new schema.

    Args:
        v3: The parsed v3 ``config.yaml``.

    Returns:
        The new config mapping and one report line per entry that could not be converted.
    """
    builtin = _mapping(v3.get("builtin_settings"))
    report: list[str] = []

    token = _mapping(v3.get("general_settings")).get("bot_token")
    if not isinstance(token, str):
        token = ""
        report.append("general_settings.bot_token: missing, token left empty")

    activities: list[dict[str, object]] = []
    for entry in _list(_mapping(builtin.get("status_changer_settings")).get("activity_messages")):
        try:
            activities.append(_activity(str(entry)))
        except ValueError as error:
            report.append(f"status: skipped {entry!r}: {error}")

    targets: list[dict[str, object]] = []
    for raw in _list(builtin.get("console_logger_settings")):
        target = _mapping(raw)
        types = [kind for kind in _list(target.get("log_type")) if kind in LOG_TYPES]
        unknown = [kind for kind in _list(target.get("log_type")) if kind not in LOG_TYPES]
        channel = target.get("channel_id")
        if not types:
            report.append(
                f"interaction_log: skipped channel {channel}: no known types in {unknown}"
            )
            continue
        if unknown:
            report.append(f"interaction_log: channel {channel}: dropped unknown types {unknown}")
        targets.append(
            {
                "guild_id": target.get("guild_id"),
                "channel_id": channel,
                "types": types,
                "format": target.get("format"),
            },
        )

    new: dict[str, object] = {
        "token": token,
        "status": {"activities": activities},
        "interaction_log": targets,
    }
    return new, report


def _activity(entry: str) -> dict[str, object]:
    """Convert ``TYPE;text;ms`` (``STREAMING;text;url[;ms]``), raising ValueError if impossible."""
    fields = entry.split(";")
    if len(fields) < 3:  # noqa: PLR2004 - TYPE, text and a third field
        msg = "expected TYPE;text;milliseconds"
        raise ValueError(msg)
    kind = ACTIVITY_TYPES.get(fields[0])
    if kind is None:
        msg = f"unknown type {fields[0]}"
        raise ValueError(msg)

    activity: dict[str, object] = {"type": kind, "text": fields[1]}
    duration = fields[2]
    if kind == "streaming":
        if not fields[2]:
            msg = "streaming needs a URL"
            raise ValueError(msg)
        activity["url"] = fields[2]
        duration = fields[3] if len(fields) > 3 else ""  # noqa: PLR2004 - optional fourth field
    if duration:
        try:
            milliseconds = int(duration)
        except ValueError:
            msg = f"duration {duration!r} is not a number"
            raise ValueError(msg) from None
        if milliseconds <= 0:
            msg = "duration must be positive"
            raise ValueError(msg)
        activity["seconds"] = milliseconds / 1000
    return activity


def _mapping(value: object) -> Mapping[str, object]:
    return cast("Mapping[str, object]", value) if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return cast("list[object]", value) if isinstance(value, list) else []


def enabled_v3_plugins(root: Path) -> list[str]:
    """Return the plugins whose v3 ``plugins/<Name>/config.yaml`` sets ``enabled: true``.

    A renamed plugin is listed under its xincord name (``RENAMED``); the names are sorted.
    """
    return sorted(
        {
            RENAMED.get(path.parent.name, path.parent.name)
            for path in (root / "plugins").glob("*/config.yaml")
            if _mapping(yaml.safe_load(path.read_text(encoding="utf-8"))).get("enabled") is True
        },
    )


def move_renamed_directories(root: Path) -> list[str]:
    """Move each renamed plugin's ``plugins/<v3 name>/`` to ``plugins/<new name>/``.

    A plugin then finds v3's config and lang files under its new name. When the new directory
    exists already, both stay as they are.

    Args:
        root: The server directory of a v3 installation.

    Returns:
        One report line per renamed plugin's v3 directory: moved, or kept.
    """
    report: list[str] = []
    for old, new in RENAMED.items():
        source, target = root / "plugins" / old, root / "plugins" / new
        if not source.is_dir():
            continue
        if target.exists():
            report.append(f"{source}: kept, {target} exists")
            continue
        source.rename(target)
        report.append(f"{source}: moved to {target}")
    return report


def set_aside_v3_configs(root: Path) -> list[str]:
    """Rename each ``SET_ASIDE`` plugin's v3 ``config.yaml`` to ``config.v3.yaml``.

    Only a file that holds no key but ``enabled`` goes; the plugin then writes its bundled
    ``config.yaml`` at its first load.

    Args:
        root: The server directory of a v3 installation.

    Returns:
        One report line per file set aside, or kept beside an existing ``config.v3.yaml``.
    """
    report: list[str] = []
    for name in SET_ASIDE:
        path = root / "plugins" / name / "config.yaml"
        backup = path.with_name("config.v3.yaml")
        if not path.is_file():
            continue
        if set(_mapping(yaml.safe_load(path.read_text(encoding="utf-8")))) - {"enabled"}:
            continue  # not v3's switch: an xincord config, or the operator's
        if backup.exists():
            report.append(f"{path}: kept, {backup} exists")
            continue
        path.rename(backup)
        report.append(f"{path}: moved to {backup}; {name} writes its bundled config")
    return report


def migrate_directory(root: Path) -> list[str]:
    """Migrate ``root/config.yaml`` in place, keeping the original as ``config.v3.yaml``.

    The renamed plugins' directories move to their new names before the new config is written,
    so that a failed move leaves the v3 config for a second run. The v3 switch files of
    ``SET_ASIDE`` plugins go last, once the plugins are listed.

    Args:
        root: The server directory of a v3 installation.

    Returns:
        Report lines describing what was done or why nothing was changed.
    """
    path, backup = root / "config.yaml", root / "config.v3.yaml"
    if not path.exists():
        return [f"{path}: not found"]
    text = path.read_text(encoding="utf-8")
    data = _mapping(yaml.safe_load(text))
    if "general_settings" not in data:
        return [f"{path}: not a v3 config, left unchanged"]
    if backup.exists():
        return [f"{backup}: already exists, {path} left unchanged"]

    new, report = migrate_core_config(data)
    plugins = enabled_v3_plugins(root)
    new = {"token": new["token"], "plugins": plugins, **new}
    report.append(f"plugins: enabled {', '.join(plugins) or 'none'}")
    CoreConfig.model_validate(new)
    moves = move_renamed_directories(root)
    backup.write_text(text, encoding="utf-8")
    path.write_text(yaml.safe_dump(new, sort_keys=False, allow_unicode=True), encoding="utf-8")
    set_aside = set_aside_v3_configs(root)
    return [*report, *moves, f"{path}: migrated, original kept as {backup}", *set_aside]


def main(argv: Sequence[str] | None = None) -> int:
    """Migrate the directory named on the command line (default: the current directory)."""
    args = sys.argv[1:] if argv is None else argv
    for line in migrate_directory(Path(args[0] if args else ".")):
        print(line)  # noqa: T201 - command-line output
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
