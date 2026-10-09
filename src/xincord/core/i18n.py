"""Localized plugin text: lang file export, loading, lookup and command translation."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from collections.abc import Mapping
    from importlib.resources.abc import Traversable
    from pathlib import Path


class LangError(Exception):
    """A plugin's lang files are missing or malformed; the message names the file and key."""


@dataclass(frozen=True)
class Lang:
    """One plugin's localized text, keyed by Discord locale (``en-US``, ``zh-TW``, ...)."""

    plugin: str
    default_locale: str
    registers: Mapping[str, Mapping[str, str]]
    texts: Mapping[str, Mapping[str, str]]
    templates: Mapping[str, Mapping[str, Path]]

    @property
    def locales(self) -> tuple[str, ...]:
        """The loaded locales, sorted."""
        return tuple(sorted(self.registers))

    @classmethod
    def load(cls, plugin: str, directory: Path, default_locale: str) -> Self:
        """Load and validate ``directory`` (a plugin's ``lang`` directory).

        Raises:
            LangError: The default locale is missing or a file is malformed.
        """
        raise NotImplementedError


def export_lang(bundled: Traversable, target: Path, *, force: bool) -> list[Path]:
    """Copy the bundled lang tree into ``target``.

    Args:
        bundled: The plugin's bundled ``lang`` directory.
        target: The plugin's ``lang`` directory on disk, created if missing.
        force: Overwrite files that already exist (``--force-renew-lang-resources``).

    Returns:
        The files written.
    """
    written: list[Path] = []
    for entry in bundled.iterdir():
        path = target / entry.name
        if entry.is_dir():
            written += export_lang(entry, path, force=force)
        elif force or not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(entry.read_bytes())
            written.append(path)
    return written
