"""Checks of the config that need several commands or the lang files, made when the plugin loads.

The models check each value; these check that names stay unique, that Discord takes the number of
commands, and that each command's template exists and can be posted.
"""

from typing import TYPE_CHECKING, cast

from pydantic import BaseModel

from xincord.core.config import ConfigError

from .config import Localization

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from pathlib import Path

    from xincord.core.i18n import Lang
    from xincord.core.templates import Templates

    from .config import CommandSpec, Config

LIMIT = 100  # Discord's slash commands per guild; discord.py's tree takes no more either
NEEDS_MORE = ("uid", "model_key")  # template keys that need component IDs or models
NONE = Localization()


def check(config: Config, lang: Lang, templates: Templates, path: Path) -> None:
    """Raise ``ConfigError`` with a line per problem, ``<file>: <key>: <problem>``.

    Args:
        config: The loaded ``config.yaml``.
        lang: The plugin's lang files.
        templates: Their parsed templates.
        path: The ``config.yaml`` file, for the messages.
    """
    commands = config.commands
    lines = [f"{path}: {problem}" for problem in _duplicate_names(commands)]
    if len(commands) > LIMIT:
        lines.append(
            f"{path}: commands: {len(commands)} commands, more than the {LIMIT} that Discord "
            "takes per guild"
        )
    lines += _template_problems(commands, lang, templates, path)
    if lines:
        raise ConfigError("\n".join(lines))


def _duplicate_names(commands: Sequence[CommandSpec]) -> Iterator[str]:
    """Each name that a command shares with an earlier one, in the default names or a locale.

    In a locale, a command shows its localized name, else its default one. Names shared by default
    names only are reported once, without a locale.
    """
    locales = sorted({locale for spec in commands for locale in spec.localizations})
    for locale in ("", *locales):
        seen: dict[str, tuple[int, bool]] = {}
        for index, spec in enumerate(commands):
            localized = spec.localizations.get(locale, NONE).name
            name = localized or spec.name
            first, first_localized = seen.setdefault(name, (index, localized is not None))
            if first == index or not (locale == "" or localized or first_localized):
                continue
            key = f"localizations.{locale}.name" if localized else "name"
            where = f"the {locale} name" if locale else "the name"
            yield f"commands.{index}.{key}: {name} is also {where} of commands.{first}"


def _template_problems(
    commands: Sequence[CommandSpec], lang: Lang, templates: Templates, path: Path
) -> Iterator[str]:
    """A command's template missing from the default locale, or one that cannot be posted."""
    checked: set[Path] = set()
    for index, spec in enumerate(commands):
        name = spec.template_name
        if f"message/{name}" not in lang.templates[lang.default_locale]:
            yield (
                f"{path}: commands.{index}.template: no {name}.yaml in "
                f"lang/{lang.default_locale}/message/"
            )
            continue
        for locale in lang.locales:
            file = lang.templates[locale].get(f"message/{name}")
            if file is None or file in checked:
                continue
            checked.add(file)
            if (key := _needs_more(templates.message(name, locale))) is not None:
                yield (
                    f"{file}: {key}: CustomCommands posts templates without component IDs (uid) "
                    "or models (model_key)"
                )


def _needs_more(node: object, key: str = "") -> str | None:
    """The key of the first ``uid`` or ``model_key`` in a parsed template, or None.

    Components with a ``uid`` need an ID builder and a handler, and a ``model_key`` a model,
    which the plugin has neither of.
    """
    if isinstance(node, BaseModel):
        for field in type(node).model_fields:
            value: object = getattr(node, field)
            path = f"{key}.{field}" if key else field
            if field in NEEDS_MORE and value is not None:
                return path
            if (found := _needs_more(value, path)) is not None:
                return found
    elif isinstance(node, tuple):
        for index, item in enumerate(cast("tuple[object, ...]", node)):
            if (found := _needs_more(item, f"{key}.{index}")) is not None:
                return found
    return None
