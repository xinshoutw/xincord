"""The listeners that post the away notice in new ticket channels while the owner is offline.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/TicketAddons.kt:11-39
    XsDiscordBotKt@3a59607:Plugins/TicketAddons/src/main/kotlin/addons/ticket/Event.kt:26-29
"""

import asyncio
from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import discord

    from xincord.core.i18n import Lang
    from xincord.core.templates import Templates

    from .config import Config

type Sleep = Callable[[float], Awaitable[object]]


class TicketAwayNotice(commands.Cog):
    """The plugin's state and listeners; ``setup`` adds them."""

    def __init__(self, bot: commands.Bot, config: Config, lang: Lang, templates: Templates) -> None:
        """Keep the bot, the config and the notice's template.

        A reload builds a new cog from the files, as v3's ``reload()`` rebuilt its template.
        """
        self.bot = bot
        self.config = config
        self.lang = lang
        self.templates = templates
        self.sleep: Sleep = asyncio.sleep  # the wait before a notice, which tests replace
        self.notices: set[asyncio.Task[None]] = set()  # the notices under way

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        """A new channel, of any kind: v3's ``ChannelCreateEvent``."""
        self.watch(channel)

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread) -> None:
        """A new thread or forum post, which JDA's ``ChannelCreateEvent`` covered too.

        discord.py dispatches it for threads created since the bot connected only; a thread the
        bot joins is ``on_thread_join``.
        """
        self.watch(thread)

    def watch(self, channel: discord.abc.GuildChannel | discord.Thread) -> None:
        """Start a notice for ``channel`` if the config watches it and it takes messages."""
        raise NotImplementedError
