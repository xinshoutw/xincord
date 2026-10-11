"""DynamicVoiceChannel: members who join a bound lobby alone get a voice room of their own."""

from typing import TYPE_CHECKING

import discord

from xincord.core.templates import Templates

from .cog import DynamicVoiceChannel

if TYPE_CHECKING:
    from xincord.core.bot import Bot

DEPENDS: tuple[str, ...] = ()
SOFT_DEPENDS: tuple[str, ...] = ()
# Voice updates and the members of each voice channel.
INTENTS = discord.Intents(voice_states=True)
# Replies use the user's locale and fall back to this one.
DEFAULT_LOCALE = "zh-TW"


async def setup(bot: Bot) -> None:
    """Load the lang files and the templates, then add the cog and its command.

    The plugin has no config. Its bindings and rooms are in the shared store.
    """
    context = bot.plugin_context(__name__)
    lang = context.lang(DEFAULT_LOCALE)
    cog = DynamicVoiceChannel(bot, context.store, lang, Templates.load(lang))
    await bot.add_cog(cog)
    # A guild command; discord.py removes it when the plugin unloads.
    bot.tree.add_command(cog.command())
