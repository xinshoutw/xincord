"""The settings menu, its components, the voice and status listeners and the checks at READY.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:29-439
"""

import asyncio
import logging
import re
from functools import partial
from typing import TYPE_CHECKING, Any, Protocol, cast, override

import discord
from discord import app_commands
from discord.ext import commands
from discord.http import Route

from xincord.core.component_ids import ComponentIds
from xincord.core.placeholders import actor_values, global_values, placeholder_values
from xincord.core.templates import render_message
from xincord.plugins.listen_channels.settings import list_text, targets
from xincord.plugins.listen_channels.store import DataError, ListenSettings

from .logs import UNKNOWN_MEMBER, Place, voice_change
from .status import ENTRIES, classify, find_actor, parse_update

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import datetime

    from xincord.core.component_ids import ParsedId
    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Message, Templates
    from xincord.plugins.listen_channels.settings import Setting
    from xincord.plugins.listen_channels.store import Kind

    from .logs import VoiceChannelLike
    from .status import Sleep

logger = logging.getLogger(__name__)

NAMESPACE = "VoiceLogger"  # the plugin's name: its settings in the store and its locks
# v3's only field, in v3's prefix, so that v3's menus keep working.
IDS = ComponentIds("voice_logger", ("action",), legacy_prefix="voice-logger@")
ROOT = "voice-logger"  # v3's command, and the root of its register.yaml keys
MENU = "voice-logger@setting"  # the settings menu's template
BUTTON = 2  # the component type of a button
ENTITY_SELECTS = frozenset({5, 6, 7, 8})  # user, role, mentionable and channel select menus
# The buttons that show a list's select menu, and the select menus that add to a list.
SELECTS = {"modify_allow_btn": "modify-allow", "modify_block_btn": "modify-block"}
MENUS: dict[str | None, Kind] = {"modify_allow_menu": "allow", "modify_block_menu": "block"}
SNOWFLAKE = re.compile(r"[0-9]+")


class Postable(Protocol):
    """A channel that takes messages, as the plugin posts its logs."""

    async def send(
        self,
        *,
        content: str | None = None,
        embeds: Sequence[discord.Embed] = (),
        view: discord.ui.View | discord.ui.LayoutView | None = None,
        files: Sequence[discord.File] = (),
    ) -> object:
        """Send a message to the channel."""
        ...


class VoiceLogger(commands.Cog):
    """The plugin's state, handlers and listeners; ``setup`` registers them."""

    def __init__(self, bot: commands.Bot, store: Store, lang: Lang, templates: Templates) -> None:
        """Keep the bot, the store and what ``setup`` loaded."""
        self.bot = bot
        self.store = store
        self.settings = ListenSettings(store, NAMESPACE)
        self.lang = lang
        self.templates = templates
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
        """Edit the deferred response into the current channel's settings menu (v3's ``setting``).

        Nothing is written: a channel without settings shows v3's default, the allow mode with
        empty lists. The command works in every channel; v3's ``Placeholder.get(event)`` threw
        outside text channels.
        """
        where = _where(interaction)
        if where is None:  # guild commands run in guilds only, as v3's handler assumed
            return
        message = self._menu(interaction, await self.settings.read_setting(*where))
        # The command tree deferred the response ephemerally, as v3's core did.
        await interaction.edit_original_response(
            content=message.content,
            embeds=message.embeds,
            view=message.view,
            attachments=message.files,
        )

    async def handle(self, interaction: discord.Interaction, parsed: ParsedId) -> None:
        """Send a press or a choice in the settings menu to its handler; ``setup`` routes here.

        As v3's two handlers, buttons take the button actions and entity select menus the select
        actions, in v3's ID format too; anything else gets no response (v3 threw for an unknown
        select action). Each answer replaces the menu's whole message, as JDA's
        ``MessageEditData.fromCreateData`` did; v3's ``deferEdit`` and edit became one request.
        """
        where = _where(interaction)
        if where is None:  # the menu exists in guilds only
            return
        data = cast("Mapping[str, object]", interaction.data or {})
        kind, action = data.get("component_type"), parsed.fields.get("action")
        if kind == BUTTON:
            await self._press(interaction, where, action)
        elif kind in ENTITY_SELECTS and action in MENUS:
            ids = _ids(data.get("values"))
            setting = await self.settings.add_channels(*where, MENUS[action], ids)
            await _edit(interaction, self._menu(interaction, setting))

    async def _press(
        self, interaction: discord.Interaction, where: tuple[int, int], action: str | None
    ) -> None:
        """Toggle the mode, show a list's select menu, or delete the settings, as v3's buttons."""
        if action == "toggle_btn":
            await _edit(interaction, self._menu(interaction, await self.settings.toggle(*where)))
        elif action in SELECTS:
            await _edit(interaction, self._render(interaction, SELECTS[action]))
        elif action == "delete_btn":
            await self.settings.remove(*where)
            await _edit(interaction, self._render(interaction, "delete"))

    def _render(self, interaction: discord.Interaction, name: str) -> Message:
        """Template ``name`` in the user's locale with v3's ``Placeholder.get(event)``."""
        template = self.templates.message(name, interaction.locale.value)
        return render_message(template, placeholder_values(interaction), build_id=IDS.build)

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
        await self._post(guild, listen, name, actor | values)

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
        await self._post(guild, listen, name, actor | values)

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
            await self.check_guilds()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Forget the statuses and check the guilds when the bot is ready, for each session.

        A new session's channels hold no status, so JDA's cache started empty again.
        """
        self.statuses.clear()
        await self.check_guilds()

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

    async def check_guilds(self) -> None:
        """Delete the settings of the guilds that the bot left, and check the others' lists.

        By ``on_ready``, discord.py knows every guild of the session, unavailable ones included.
        v3's ``JsonManager`` deleted the files of the guilds it did not know at its first use,
        inside a loop that then threw. An unavailable guild (an outage) is left alone: discord.py
        knows it without its channels.
        """
        for guild_id in await self.settings.guild_ids():
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                await self.settings.forget(guild_id)
                logger.info(
                    "VoiceLogger deleted the settings of guild %s, which the bot left", guild_id
                )
            elif not guild.unavailable:
                await self._check(guild)

    async def _check(self, guild: discord.Guild) -> None:
        """Drop the channels that ``guild`` no longer has from its lists, as v3's startup did.

        Listen channels are not checked: a deleted one is forgotten when a log finds it gone,
        and a thread is not cached while it is archived. A guild whose settings cannot be read is
        skipped with an error, so that the others are still checked.
        """
        known = {channel.id for channel in guild.channels}
        try:
            dropped = await self.settings.prune(guild.id, known)
        except DataError:
            logger.exception("VoiceLogger cannot check the settings of guild %s", guild.id)
            return
        if dropped:
            logger.info(
                "VoiceLogger dropped the deleted channels %s from the lists of %s (%s)",
                ", ".join(map(str, dropped)),
                guild.name,
                guild.id,
            )

    async def _post(
        self, guild: discord.Guild, listen: Sequence[int], name: str, values: Mapping[str, str]
    ) -> None:
        """Send template ``name`` to each listen channel of ``listen``, in the guild's locale.

        v3 used ``guild.locale``; the templates fall back to zh-TW. Each channel gets its own
        render, because discord.py closes a message's files once sent, and is reached without
        the cache. A channel that Discord no longer has loses its settings; a refusal is a
        warning; the other channels still get the log. v3 stopped at the first missing channel
        and threw for channels other than text and voice channels.
        """
        template = self.templates.message(name, guild.preferred_locale.value)
        for channel_id in listen:
            partial = self.bot.get_partial_messageable(channel_id, guild_id=guild.id)
            channel = cast("Postable", partial)  # send's overloads never take a view union
            message = render_message(template, values, build_id=IDS.build)
            try:
                await channel.send(
                    content=message.content or None,
                    embeds=message.embeds,
                    view=message.view,
                    files=message.files,
                )
            except discord.NotFound:
                await self.settings.remove(guild.id, channel_id)
                logger.info(
                    "VoiceLogger forgot the listen channel %s of %s (%s), which no longer exists",
                    channel_id,
                    guild.name,
                    guild.id,
                )
            except discord.HTTPException as error:
                logger.warning(
                    "VoiceLogger cannot post in the listen channel %s of %s (%s): %s",
                    channel_id,
                    guild.name,
                    guild.id,
                    error,
                )

    def _menu(self, interaction: discord.Interaction, setting: Setting) -> Message:
        """v3's settings menu for ``setting``, in the user's locale.

        The values are v3's ``Placeholder.get(event)``, the mode and both lists, each in the
        locale's line format from ``placeholder.yaml``.
        """
        locale = interaction.locale.value
        values = placeholder_values(interaction)
        empty = self.lang.text("placeholder.empty", locale)
        lists = {
            f"vl_{kind}_list_format": list_text(
                ids,
                self.lang.text(f"placeholder.{kind}_list_format", locale),
                empty,
                values,
                f"{kind}list",
            )
            for kind, ids in (("allow", setting.allow), ("block", setting.block))
        }
        mode = {"vl_channel_mode": "ALLOW" if setting.allow_mode else "BLOCK"}
        template = self.templates.message(MENU, locale)
        return render_message(template, values | mode | lists, build_id=IDS.build)


async def _edit(interaction: discord.Interaction, message: Message) -> None:
    """Replace the component's whole message with ``message``."""
    await interaction.response.edit_message(
        content=message.content,
        embeds=message.embeds,
        view=message.view,
        attachments=message.files,
    )


def _ids(values: object) -> list[int]:
    """The channel and category IDs that a select menu sent, as Discord's decimal strings."""
    entries = cast("list[object]", values) if isinstance(values, list) else []
    return [
        int(entry) for entry in entries if isinstance(entry, str) and SNOWFLAKE.fullmatch(entry)
    ]


def _place(channel: VoiceChannelLike | None) -> Place | None:
    """What the logs show of a voice state's channel, if the member is in one."""
    return None if channel is None else Place.of(channel)


def _where(interaction: discord.Interaction) -> tuple[int, int] | None:
    """The guild and the channel of ``interaction``, the listen channel's place, if in a guild."""
    guild_id, channel_id = interaction.guild_id, interaction.channel_id
    return None if guild_id is None or channel_id is None else (guild_id, channel_id)
