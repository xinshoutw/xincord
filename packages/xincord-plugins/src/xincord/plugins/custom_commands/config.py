"""The plugin's ``config.yaml``: the commands, which v3 fixed in its code.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/command/Register.kt:9-60
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/command/CmdFileSerializer.kt:7-23
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/resources/lang/zh-TW/register.yaml:1-19
"""

from pydantic import Field

from xincord.core.config import Model


class Localization(Model):
    """A command's name and description in one Discord locale; either may be left out."""

    name: str | None = None
    description: str | None = None


class CommandSpec(Model):
    """One command: what Discord shows of it, who sees it and where."""

    name: str
    description: str
    # Per Discord locale (zh-TW, en-US, ...).
    localizations: dict[str, Localization] = Field(default_factory=dict[str, Localization])
    # discord.py's permission names; v3's commands were for administrators.
    permissions: tuple[str, ...] = ("administrator",)
    guilds: tuple[int, ...] = ()  # the guilds that get the command; empty for every guild


class Config(Model):
    """``plugins/CustomCommands/config.yaml``; the bundled file lists v3's five commands.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin.
    """

    commands: tuple[CommandSpec, ...] = ()
