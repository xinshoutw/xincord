"""The settings menu and its components, the posts to listen channels and the checks at READY."""

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

import discord

from xincord.core.placeholders import placeholder_values
from xincord.core.templates import render_message

from .settings import list_text
from .store import DataError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from discord.ext import commands

    from xincord.core.component_ids import ComponentIds, ParsedId
    from xincord.core.i18n import Lang
    from xincord.core.templates import Message, Templates

    from .settings import Setting
    from .store import Kind, ListenSettings

logger = logging.getLogger(__name__)

BUTTON = 2  # the component type of a button
ENTITY_SELECTS = frozenset({5, 6, 7, 8})  # user, role, mentionable and channel select menus
# The buttons that show a list's select menu, and the select menus that add to a list.
SELECTS = {"modify_allow_btn": "modify-allow", "modify_block_btn": "modify-block"}
MENUS: dict[str | None, Kind] = {"modify_allow_menu": "allow", "modify_block_menu": "block"}
SNOWFLAKE = re.compile(r"[0-9]+")


class Postable(Protocol):
    """A channel that takes messages, as the plugins post their logs."""

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


@dataclass(frozen=True)
class Menu:
    """What a plugin's settings menu is made of; the plugins differ in these only."""

    lang: Lang
    templates: Templates
    ids: ComponentIds  # the components' IDs, which also read v3's
    key: str  # the prefix of the menu's values in v3's templates: vl or cl
    template: str  # the menu's template, such as voice-logger@setting


class ListenChannels:
    """A plugin's listen channels: their settings menu, its components, the posts and the checks.

    The plugin's cog calls it from its command, its component route and its listeners.
    """

    def __init__(self, bot: commands.Bot, settings: ListenSettings, menu: Menu) -> None:
        """Keep the bot, the plugin's settings and its menu."""
        self.bot = bot
        self.settings = settings
        self.menu = menu

    async def show(self, interaction: discord.Interaction) -> None:
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
        """Send a press or a choice in the settings menu to its handler.

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

    async def post(
        self, guild: discord.Guild, listen: Sequence[int], name: str, values: Mapping[str, str]
    ) -> set[int]:
        """Send template ``name`` to each listen channel of ``listen``, in the guild's locale.

        v3 used ``guild.locale``; the templates fall back to zh-TW. Each channel gets its own
        render, because discord.py closes a message's files once sent, and is reached without
        the cache. A channel that Discord no longer has loses its settings; a refusal is a
        warning; the other channels still get the log. v3 stopped at the first missing channel
        and threw for channels other than text and voice channels. Return the channels that are
        gone or forbid the bot, which further logs of the same event need not try.
        """
        template = self.menu.templates.message(name, guild.preferred_locale.value)
        plugin = self.settings.namespace
        failed: set[int] = set()
        for channel_id in listen:
            partial = self.bot.get_partial_messageable(channel_id, guild_id=guild.id)
            channel = cast("Postable", partial)  # send's overloads never take a view union
            message = render_message(template, values, build_id=self.menu.ids.build)
            try:
                await channel.send(
                    content=message.content or None,
                    embeds=message.embeds,
                    view=message.view,
                    files=message.files,
                )
            except discord.NotFound:
                failed.add(channel_id)
                await self.settings.remove(guild.id, channel_id)
                logger.info(
                    "%s forgot the listen channel %s of %s (%s), which no longer exists",
                    plugin,
                    channel_id,
                    guild.name,
                    guild.id,
                )
            except discord.HTTPException as error:
                if isinstance(error, discord.Forbidden):
                    failed.add(channel_id)
                logger.warning(
                    "%s cannot post in the listen channel %s of %s (%s): %s",
                    plugin,
                    channel_id,
                    guild.name,
                    guild.id,
                    error,
                )
        return failed

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
                    "%s deleted the settings of guild %s, which the bot left",
                    self.settings.namespace,
                    guild_id,
                )
            elif not guild.unavailable:
                await self._check(guild)

    async def _check(self, guild: discord.Guild) -> None:
        """Drop the channels that Discord no longer has from the guild's lists, as v3's start did.

        discord.py caches the guild's channels and its active threads; a listed ID that it has
        not cached, such as an archived thread, is asked of Discord, and dropped only when Discord
        answers that it does not exist. Listen channels are not checked: a deleted one is
        forgotten when a log finds it gone. A guild whose settings cannot be read is skipped with
        an error, so that the others are still checked.
        """
        plugin = self.settings.namespace
        cached = {channel.id for channel in (*guild.channels, *guild.threads)}
        try:
            settings = await self.settings.read_settings(guild.id)
            listed = {item for entry in settings.values() for item in (*entry.allow, *entry.block)}
            gone = {item for item in sorted(listed - cached) if await self._gone(item)}
            dropped = await self.settings.prune(guild.id, gone)
        except DataError:
            logger.exception("%s cannot check the settings of guild %s", plugin, guild.id)
            return
        if dropped:
            logger.info(
                "%s dropped the deleted channels %s from the lists of %s (%s)",
                plugin,
                ", ".join(map(str, dropped)),
                guild.name,
                guild.id,
            )

    async def _gone(self, channel_id: int) -> bool:
        """Whether Discord answers that the channel does not exist.

        Any other refusal, such as a private thread that the bot cannot see, or an outage, keeps
        the channel.
        """
        try:
            await self.bot.http.get_channel(channel_id)
        except discord.NotFound:
            return True
        except discord.HTTPException:
            return False
        return False

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
        template = self.menu.templates.message(name, interaction.locale.value)
        return render_message(
            template, placeholder_values(interaction), build_id=self.menu.ids.build
        )

    def _menu(self, interaction: discord.Interaction, setting: Setting) -> Message:
        """v3's settings menu for ``setting``, in the user's locale.

        The values are v3's ``Placeholder.get(event)``, the mode and both lists, each in the
        locale's line format from ``placeholder.yaml``.
        """
        menu, locale = self.menu, interaction.locale.value
        values = placeholder_values(interaction)
        empty = menu.lang.text("placeholder.empty", locale)
        lists = {
            f"{menu.key}_{kind}_list_format": list_text(
                ids,
                menu.lang.text(f"placeholder.{kind}_list_format", locale),
                empty,
                values,
                f"{kind}list",
            )
            for kind, ids in (("allow", setting.allow), ("block", setting.block))
        }
        mode = {f"{menu.key}_channel_mode": "ALLOW" if setting.allow_mode else "BLOCK"}
        template = menu.templates.message(menu.template, locale)
        return render_message(template, values | mode | lists, build_id=menu.ids.build)


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


def _where(interaction: discord.Interaction) -> tuple[int, int] | None:
    """The guild and the channel of ``interaction``, the listen channel's place, if in a guild."""
    guild_id, channel_id = interaction.guild_id, interaction.channel_id
    return None if guild_id is None or channel_id is None else (guild_id, channel_id)
