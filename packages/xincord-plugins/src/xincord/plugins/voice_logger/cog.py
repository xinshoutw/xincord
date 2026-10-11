"""The command, the voice and status listeners, and the shared listen channel code's wiring."""

import asyncio
import logging
from functools import partial
from typing import TYPE_CHECKING, Any, override

import discord
from discord import app_commands
from discord.ext import commands
from discord.http import Route

from xincord.core.component_ids import ComponentIds
from xincord.core.placeholders import actor_values, global_values
from xincord.plugins.listen_channels.menu import ListenChannels, Menu
from xincord.plugins.listen_channels.settings import targets
from xincord.plugins.listen_channels.store import ListenSettings

from .logs import UNKNOWN_MEMBER, Place, voice_change
from .status import ENTRIES, classify, find_actor, parse_update

if TYPE_CHECKING:
    from datetime import datetime

    from xincord.core.component_ids import ParsedId
    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Templates

    from .logs import VoiceChannelLike
    from .status import Sleep

logger = logging.getLogger(__name__)

NAMESPACE = "VoiceLogger"  # the plugin's name: its settings in the store and its locks
# v3's only field, in v3's prefix, so that v3's menus keep working.
IDS = ComponentIds("voice_logger", ("action",), legacy_prefix="voice-logger@")
ROOT = "voice-logger"  # v3's command, and the root of its register.yaml keys
MENU = "voice-logger@setting"  # the settings menu's template


class VoiceLogger(commands.Cog):
    """The plugin's state, handlers and listeners; ``setup`` registers them."""

    def __init__(self, bot: commands.Bot, store: Store, lang: Lang, templates: Templates) -> None:
        """Keep the bot, the store and what ``setup`` loaded."""
        self.bot = bot
        self.store = store
        self.lang = lang
        self.settings = ListenSettings(store, NAMESPACE)
        # The menu, its components, the posts and the checks at READY, shared with ChatLogger.
        self.listen = ListenChannels(bot, self.settings, Menu(lang, templates, IDS, "vl", MENU))
        # Each guild's voice channel statuses from Discord's updates in this session, as JDA's
        # cache kept them; empty ones are left out.
        self.statuses: dict[int, dict[int, str]] = {}
        self.sleep: Sleep = asyncio.sleep  # before the audit log is read again

    def command(self) -> app_commands.Group:
        """Build v3's ``/voice-logger`` with its subcommand ``setting``, from ``register.yaml``.

        As in v3, only administrators see it by default; there is no other check. The group is
        built here, so its module is the plugin's and unloading the plugin removes it.
        """
        lang = self.lang
        group = app_commands.Group(
            name=lang.command(ROOT, f"{ROOT}.name"),
            description=lang.command("commands about voice logger", f"{ROOT}.description"),
            default_permissions=discord.Permissions(administrator=True),
        )
        key = f"{ROOT}.subcommands.setting"
        setting: app_commands.Command[Any, ..., None] = app_commands.Command(
            name=lang.command("setting", f"{key}.name"),
            description=lang.command("set voice log in this channel", f"{key}.description"),
            callback=self.show_settings,
        )
        group.add_command(setting)
        return group

    async def show_settings(self, interaction: discord.Interaction) -> None:
        """Edit the deferred response into the channel's settings menu (v3's ``setting``)."""
        await self.listen.show(interaction)

    async def handle(self, interaction: discord.Interaction, parsed: ParsedId) -> None:
        """Change the settings from the menu's buttons and select menus; ``setup`` routes here."""
        await self.listen.handle(interaction, parsed)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        """Post a join, a leave or a switch to the listen channels that detect it.

        The channels are read at once, before anything awaits: discord.py runs listeners as tasks,
        and later events change its cache meanwhile. The member is the one whose state changed,
        bots included, also when a moderator moved them (v3's ``Placeholder.get(member)``).
        """
        joined, left = _place(after.channel), _place(before.channel)
        change = voice_change(joined, left)
        if change is None:
            return
        name, values = change
        guild = member.guild
        sides = [(place.id, place.category_id) for place in (joined, left) if place is not None]
        listen = targets(await self.settings.read_settings(guild.id), sides)
        bot = self.bot.user
        actor = {} if bot is None else actor_values(member, bot)
        await self.listen.post(guild, listen, name, actor | values)

    @commands.Cog.listener()
    async def on_gateway_voice_channel_status_update(self, payload: dict[str, object]) -> None:
        """Post a voice channel's status change to the listen channels that detect the channel.

        ``setup`` relays the gateway event, which discord.py does not parse. Statuses are tracked
        from these events, as JDA's channel cache did: Discord sends them in no channel object, so
        a status not seen in this session is empty. Only cached voice channels count, as JDA's
        ``VoiceChannel`` lookup. The cache is read before anything awaits, and one channel's
        changes are posted in the order they arrive, also when one waits for its audit log entry.
        """
        update = parse_update(payload)
        if update is None:
            logger.warning(
                "VoiceLogger ignored a malformed voice channel status update: %r", payload
            )
            return
        guild = self.bot.get_guild(update.guild_id)
        channel = None if guild is None else guild.get_channel(update.channel_id)
        if guild is None or channel is None or channel.type is not discord.ChannelType.voice:
            return
        known = self.statuses.setdefault(guild.id, {})
        old = known.pop(channel.id, "")
        if update.status:
            known[channel.id] = update.status
        name = classify(old, update.status)
        if name is None:
            return
        place, at = Place.of(channel), discord.utils.utcnow()
        # The lock hands the channel's changes over in arrival order.
        async with self.store.lock(f"{NAMESPACE}:status:{place.id}"):
            await self._log_status(guild, place, name, (old, update.status), at)

    async def _log_status(
        self, guild: discord.Guild, place: Place, name: str, change: tuple[str, str], at: datetime
    ) -> None:
        """Post template ``name`` of a status change from ``change[0]`` to ``change[1]``.

        The audit log and the member are read only when a listen channel detects the channel; v3
        read them first, for nothing.
        """
        listen = targets(
            await self.settings.read_settings(guild.id), [(place.id, place.category_id)]
        )
        if not listen:
            return
        old, new = change
        values = {
            "vl_channel_mention": place.mention,
            "vl_channel_url": place.url,
            "vl_category_mention": place.category_mention,
            "vl_status_before": old,
            "vl_status_after": new,
        }
        member = await self._status_member(guild, place.id, new, at)
        bot = self.bot.user
        actor = (
            global_values(self.bot) | UNKNOWN_MEMBER
            if member is None or bot is None
            else actor_values(member, bot)
        )
        await self.listen.post(guild, listen, name, actor | values)

    async def _status_member(
        self, guild: discord.Guild, channel_id: int, status: str, at: datetime
    ) -> discord.Member | None:
        """The member who set ``status`` on the channel, from the audit log, if it tells.

        v3's ``retrieveMemberById``: the member is fetched from Discord. A user who left the
        guild, or an audit log without the entry, gives no member.
        """
        fetch = partial(self._audit_log, guild)
        user_id = await find_actor(fetch, channel_id, status, at, self.sleep)
        if user_id is None:
            return None
        try:
            return await guild.fetch_member(user_id)
        except discord.HTTPException:
            return None

    async def _audit_log(self, guild: discord.Guild, kind: int) -> object | None:
        """The guild's newest audit log entries of type ``kind``, or None when Discord refuses.

        discord.py's ``Guild.audit_logs`` drops the channel and the status of types 192 and 193,
        which it does not know, so the request goes through its HTTP client as it is.
        """
        route = Route("GET", "/guilds/{guild_id}/audit-logs", guild_id=guild.id)
        try:
            return await self.bot.http.request(
                route, params={"action_type": kind, "limit": ENTRIES}
            )
        except discord.HTTPException as error:
            logger.warning(
                "VoiceLogger cannot read the audit log of %s (%s): %s", guild.name, guild.id, error
            )
            return None

    @override
    async def cog_load(self) -> None:
        """Check the guilds at once when the plugin loads into a ready bot, as on a reload."""
        if self.bot.is_ready():
            await self.listen.check_guilds()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Forget the statuses and check the guilds when the bot is ready, for each session.

        A new session's channels hold no status, so JDA's cache started empty again.
        """
        self.statuses.clear()
        await self.listen.check_guilds()

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Delete the settings of a guild that the bot left or was removed from.

        v3 handled no leave and deleted the guild's file at its next start. discord.py does not
        fire this during an outage (``on_guild_unavailable``).
        """
        self.statuses.pop(guild.id, None)
        await self.settings.forget(guild.id)

    @commands.Cog.listener()
    async def on_guild_unavailable(self, guild: discord.Guild) -> None:
        """Forget the guild's statuses during an outage: its channels come back without them."""
        self.statuses.pop(guild.id, None)


def _place(channel: VoiceChannelLike | None) -> Place | None:
    """What the logs show of a voice state's channel, if the member is in one."""
    return None if channel is None else Place.of(channel)
