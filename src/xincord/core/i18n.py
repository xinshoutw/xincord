"""Localized plugin text: lang file export, loading, lookup and command translation."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from importlib.resources.abc import Traversable
    from pathlib import Path


def export_lang(bundled: Traversable, target: Path, *, force: bool) -> list[Path]:
    """Copy the bundled lang tree into ``target``.

    Args:
        bundled: The plugin's bundled ``lang`` directory.
        target: The plugin's ``lang`` directory on disk, created if missing.
        force: Overwrite files that already exist (``--force-renew-lang-resources``).

    Returns:
        The files written.
    """
    raise NotImplementedError
