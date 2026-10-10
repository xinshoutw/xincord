"""The plugin's ``config.yaml``: the commands, which v3 fixed in its code.

Each value is checked here against what Discord and discord.py take, so that a mistake names its
key when the plugin loads instead of failing at each use or at the upload.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/command/Register.kt:9-60
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/command/CmdFileSerializer.kt:7-23
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/lang/zh-TW/register.yaml:1-19
"""

from typing import Annotated, Literal

import discord
from discord.app_commands.commands import validate_name
from pydantic import AfterValidator, Field, PositiveInt, StringConstraints

from xincord.core.config import Model
from xincord.core.i18n import DESCRIPTION_MAX, is_command_name

LOCALES = frozenset(locale.value for locale in discord.Locale)


def _name(name: str) -> str:
    """Accept ``name`` if discord.py and Discord both take it as a command's name.

    discord.py's check, which ``app_commands.Command`` runs too, refuses an apostrophe, which
    Discord takes, but lets a final line break through, which Discord refuses.
    """
    validate_name(name)
    if not is_command_name(name):
        msg = "a name has 1 to 32 characters: lower-case letters, digits, - and _"
        raise ValueError(msg)
    return name


def _localized_name(name: str) -> str:
    """Accept ``name`` if it follows Discord's command name rules, as ``register.yaml`` names."""
    if not is_command_name(name):
        msg = "a name has 1 to 32 characters: lower-case letters, digits, -, _ and '"
        raise ValueError(msg)
    return name


def _locale(value: str) -> str:
    """Accept ``value`` if it is a Discord locale."""
    if value not in LOCALES:
        msg = f"{value} is not a Discord locale, such as zh-TW or en-US"
        raise ValueError(msg)
    return value


def _permission(name: str) -> str:
    """Accept ``name`` if it is one of discord.py's permission names."""
    if name not in discord.Permissions.VALID_FLAGS:
        msg = f"{name} is not a permission, such as administrator or manage_guild"
        raise ValueError(msg)
    return name


Name = Annotated[str, AfterValidator(_name)]
Description = Annotated[str, StringConstraints(min_length=1, max_length=DESCRIPTION_MAX)]


class Localization(Model):
    """A command's name and description in one Discord locale; either may be left out."""

    name: Annotated[str, AfterValidator(_localized_name)] | None = None
    description: Description | None = None


class CommandSpec(Model):
    """One command: what Discord shows of it, who sees it and where."""

    name: Name
    description: Description
    localizations: dict[Annotated[str, AfterValidator(_locale)], Localization] = Field(
        default_factory=dict[str, Localization]
    )
    # The message template it posts, lang/<locale>/message/<template>.yaml; v3 named each one
    # after its command.
    template: str | None = None
    # discord.py's permission names; v3's commands were for administrators.
    permissions: tuple[Annotated[str, AfterValidator(_permission)], ...] = ("administrator",)
    # Where the message goes: a post in the command's channel (v3's way), a public reply, or a
    # reply that only the user sees.
    reply: Literal["channel", "public", "ephemeral"] = "channel"
    guilds: tuple[PositiveInt, ...] = ()  # the guilds that get the command; empty for every guild

    @property
    def template_name(self) -> str:
        """The name of the message template that the command posts."""
        return self.template or self.name


class Config(Model):
    """``plugins/CustomCommands/config.yaml``; the bundled file lists v3's five commands.

    ``commands`` is required: the bundled file holds v3's commands, whose zh-TW names Python
    cannot hold, and a file without the key, such as v3's (only ``enabled``), names it.
    """

    commands: tuple[CommandSpec, ...]
