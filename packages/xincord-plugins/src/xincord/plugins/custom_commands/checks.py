"""Checks of the config that need several commands or the lang files, made when the plugin loads.

The models check each value; these check that names stay unique, that Discord takes the number of
commands, and that each command's template exists and can be posted.
"""

from typing import TYPE_CHECKING

from xincord.core.config import ConfigError
from xincord.core.templates import TemplateError, render_message

from .config import Localization

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from pathlib import Path

    from xincord.core.i18n import Lang
    from xincord.core.templates import MessageTemplate, Templates

    from .config import CommandSpec, Config

# Discord's slash commands per guild. discord.py's tree takes no more either, and the core keeps
# every plugin's commands in it.
LIMIT = 100
NONE = Localization()


def check(config: Config, lang: Lang, templates: Templates, path: Path, *, taken: int) -> None:
    """Raise ``ConfigError`` with a line per problem, ``<file>: <key>: <problem>``.

    Args:
        config: The loaded ``config.yaml``.
        lang: The plugin's lang files.
        templates: Their parsed templates.
        path: The ``config.yaml`` file, for the messages.
        taken: How many slash commands the bot holds already (the core's, other plugins').
    """
    commands = config.commands
    lines = [f"{path}: {problem}" for problem in _duplicate_names(commands)]
    if len(commands) > (room := LIMIT - taken):
        lines.append(
            f"{path}: commands: {len(commands)} commands, more than the {room} places left of "
            f"the {LIMIT} that Discord takes per guild"
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
            if (problem := _render_problem(templates.message(name, locale))) is not None:
                yield f"{file}: cannot be posted: {problem}"


def _render_problem(template: MessageTemplate) -> str | None:
    """Why ``template`` cannot be rendered as the plugin renders it, or None.

    The plugin has no component IDs and no models to give, so a component with a ``uid`` or a
    ``model_key`` fails, as do a missing ``file_path`` and too many rows or components. The
    render has no placeholder values; the files it opens are closed.
    """
    try:
        message = render_message(template, {})
    except (TemplateError, ValueError) as error:
        return str(error)
    for file in message.files:
        file.close()
    return None
