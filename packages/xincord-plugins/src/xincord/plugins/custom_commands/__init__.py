"""CustomCommands: the commands of the config post message templates.

The bundled config lists v3's five administrator commands, which post a shop's bank payment
instructions in the channel.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/Event.kt:14-62
"""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .checks import check
from .cog import CustomCommands
from .config import Config

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
INTENTS = discord.Intents.none()
# v3's only locale. The messages are public, so every user gets them in it, as in v3.
DEFAULT_LOCALE = "zh-TW"


async def setup(bot: Bot) -> None:
    """Load the lang files, the templates and the config, then add the cog and its commands.

    The lang files load first, so that the templates are written even when the config is broken.
    The config is checked against itself and the templates (``checks.check``), so that a mistake
    disables the plugin with its key named.
    """
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    templates = Templates.load(lang)
    config = context.config(Config)
    check(config, lang, templates, context.directory / "config.yaml")
    cog = CustomCommands(config, lang, templates)
    await bot.add_cog(cog)
    # Guild commands, as in v3, in the config's order. discord.py removes them when the plugin
    # unloads.
    for spec in cog.config.commands:
        bot.tree.add_command(cog.command(spec))
