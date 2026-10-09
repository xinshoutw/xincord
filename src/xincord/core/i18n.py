"""Localized plugin text: lang file export, loading, lookup and command translation."""

import logging
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self, cast

import discord
import yaml
from discord import app_commands

if TYPE_CHECKING:
    from collections.abc import Mapping
    from importlib.resources.abc import Traversable
    from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATE_KINDS = ("message", "modal")
YAML_SUFFIXES = (".yml", ".yaml")
NAME_MAX = 32
DESCRIPTION_MAX = 100


class LangError(Exception):
    """A plugin's lang files are missing or malformed; the message names the file and key."""


@dataclass(frozen=True, eq=False)
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
        registers: dict[str, Mapping[str, str]] = {}
        texts: dict[str, Mapping[str, str]] = {}
        templates: dict[str, Mapping[str, Path]] = {}
        for entry in sorted(directory.iterdir()) if directory.is_dir() else ():
            if not entry.is_dir():
                continue
            try:
                locale = discord.Locale(entry.name).value
            except ValueError:
                logger.warning("%s: skipped %s, not a Discord locale", plugin, entry)
                continue
            registers[locale], texts[locale], templates[locale] = _load_locale(entry)

        if default_locale not in registers:
            msg = f"{plugin}: no lang directory for the default locale {default_locale}"
            raise LangError(msg)
        for kind, tables in (("register", registers), ("text", texts), ("template", templates)):
            _compare_keys(plugin, default_locale, kind, tables)
        return cls(plugin, default_locale, registers, texts, templates)

    def text(self, key: str, locale: str) -> str:
        """Return a text (``<file stem>.<path>``) in ``locale``, else in the default locale.

        Raises:
            LookupError: Neither locale has the key.
        """
        raise NotImplementedError

    def template(self, name: str, locale: str) -> Path:
        """Return the file of a template (``message/<stem>``), falling back like :meth:`text`.

        Raises:
            LookupError: Neither locale has the template.
        """
        raise NotImplementedError

    def localization(self, key: str, locale: str) -> str | None:
        """Return a ``register.yaml`` value in exactly ``locale``, without fallback."""
        raise NotImplementedError

    def command(self, default: str, key: str) -> app_commands.locale_str:
        """Return a command string that :class:`Translator` resolves through ``key``."""
        raise NotImplementedError


class Translator(app_commands.Translator):
    """Resolves command strings created by :meth:`Lang.command`."""

    async def translate(
        self,
        string: app_commands.locale_str,
        locale: discord.Locale,
        context: app_commands.TranslationContextTypes,
    ) -> str | None:
        """Return the string's register value in ``locale``, or None to keep the default."""
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


def _load_locale(directory: Path) -> tuple[dict[str, str], dict[str, str], dict[str, Path]]:
    register: dict[str, str] = {}
    texts: dict[str, str] = {}
    for path in sorted(directory.iterdir()):
        if not (path.is_file() and path.suffix in YAML_SUFFIXES):
            continue
        flat = _flatten(path)
        if path.stem == "register":
            _check_register(path, flat)
            register = flat
        else:
            texts |= {f"{path.stem}.{key}": value for key, value in flat.items()}

    templates: dict[str, Path] = {}
    for kind in TEMPLATE_KINDS:
        folder = directory / kind
        for path in sorted(folder.iterdir()) if folder.is_dir() else ():
            if path.suffix not in YAML_SUFFIXES:
                continue
            name = f"{kind}/{path.stem}"
            if name in templates:
                msg = f"{path}: duplicate template {name}"
                raise LangError(msg)
            templates[name] = path
    return register, texts, templates


def _flatten(path: Path) -> dict[str, str]:
    try:
        data: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        msg = f"{path}: invalid YAML: {error}"
        raise LangError(msg) from error
    if data is None:
        return {}
    if not isinstance(data, dict):
        msg = f"{path}: expected a mapping at the top level"
        raise LangError(msg)

    flat: dict[str, str] = {}

    def walk(node: Mapping[object, object], prefix: str) -> None:
        for key, value in node.items():
            dotted = f"{prefix}{key}"
            if isinstance(value, str):
                flat[dotted] = value
            elif isinstance(value, dict):
                walk(cast("Mapping[object, object]", value), f"{dotted}.")
            else:
                msg = f"{path}: {dotted}: expected text, got {type(value).__name__}"
                raise LangError(msg)

    walk(cast("Mapping[object, object]", data), "")
    return flat


def _check_register(path: Path, flat: Mapping[str, str]) -> None:
    for key, value in flat.items():
        field = key.rpartition(".")[2]
        if field == "name" and not _is_command_name(value):
            msg = f"{path}: {key}: {value!r} is not a valid Discord command name"
            raise LangError(msg)
        if field == "description" and not 0 < len(value) <= DESCRIPTION_MAX:
            msg = f"{path}: {key}: a description needs 1 to {DESCRIPTION_MAX} characters"
            raise LangError(msg)


def _is_command_name(name: str) -> bool:
    return (
        0 < len(name) <= NAME_MAX
        and name == name.lower()
        and all(char in "-_'" or unicodedata.category(char)[0] in "LNM" for char in name)
    )


def _compare_keys(
    plugin: str,
    default_locale: str,
    kind: str,
    tables: Mapping[str, Mapping[str, object]],
) -> None:
    expected = tables[default_locale].keys()
    for locale, table in tables.items():
        if missing := sorted(expected - table.keys()):
            logger.warning(
                "%s: %s lacks %s keys of %s: %s",
                plugin,
                locale,
                kind,
                default_locale,
                ", ".join(missing),
            )
        if extra := sorted(table.keys() - expected):
            logger.warning(
                "%s: %s has %s keys that %s lacks: %s",
                plugin,
                locale,
                kind,
                default_locale,
                ", ".join(extra),
            )
