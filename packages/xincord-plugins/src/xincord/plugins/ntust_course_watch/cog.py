"""The plugin's cog: the commands, the loop and the posts.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/Event.kt:14-61
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/NtustCourse.kt:15-142
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/command/Register.kt:12-28
"""

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, NamedTuple, override

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from xincord.plugins.failures import Failures

from .courses import course_code
from .store import Registrations
from .texts import course_list, text
from .watch import Watcher, describe
from .web import open_api

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from contextlib import AbstractAsyncContextManager

    from xincord.core.i18n import Lang
    from xincord.core.storage import Store

    from .alerts import Post
    from .config import Config
    from .web import Query

type OpenApi = Callable[[], AbstractAsyncContextManager[Query]]
type Sleep = Callable[[float], Awaitable[object]]

logger = logging.getLogger(__name__)

MIN_PAUSE = 0.1  # v3's 100 ms at least between two requests
# A post that Discord refused or that did not reach it.
POST_ERRORS = (discord.HTTPException, aiohttp.ClientError, OSError)


class CommandSpec(NamedTuple):
    """One of v3's commands: its ``register.yaml`` key and v3's texts."""

    key: str
    description: str
    option: str | None = None  # the description of v3's ``id`` option, if the command has it


# v3's commands, in v3's order.
COMMANDS = {
    "course-add": CommandSpec("course_add", "add a course", "the course code to add"),
    "course-remove": CommandSpec("course_remove", "remove a course", "the course code to remove"),
    "course-list": CommandSpec("course_list", "list all courses"),
}


class NtustCourseWatch(commands.Cog):
    """The plugin's state and commands; ``setup`` adds them."""

    def __init__(self, bot: commands.Bot, config: Config, store: Store, lang: Lang) -> None:
        """Keep the bot, the config, the registrations and the texts.

        A reload builds a new cog from the new config.
        """
        self.bot = bot
        self.config = config
        self.registrations = Registrations(store)
        self.lang = lang
        self.tasks: tuple[asyncio.Task[None], ...] = ()  # the loop, from READY
        self.posting: set[asyncio.Task[None]] = set()  # the alerts on their way
        # The effects that tests replace: the waits, the clocks and the course query.
        self.sleep: Sleep = asyncio.sleep
        self.clock: Callable[[], float] = time.monotonic
        self.now: Callable[[], datetime] = lambda: datetime.now(UTC)
        self.open_api: OpenApi = open_api
        self.posts: dict[int, Failures] = {}  # each channel's refusals, logged once per episode

    @override
    async def cog_load(self) -> None:
        """Start the loop; it waits until the bot is ready.

        ``setup`` runs before the gateway connects, and ``--no-online`` never connects, so nothing
        is asked before READY. In a ready bot, as after a reload, the loop starts at once: v3
        started its monitor when it loaded, after JDA was ready.
        """
        task = asyncio.create_task(self._run(), name="NtustCourseWatch")
        task.add_done_callback(_ended)
        self.tasks = (task,)

    @override
    async def cog_unload(self) -> None:
        """Cancel the loop and the posts under way and wait for them, so that the session closes.

        A reload builds a new cog with the new config; v3's reload added a second subscriber to
        the monitor, which doubled every alert.
        """
        running = (*self.tasks, *self.posting)
        for task in running:
            task.cancel()
        await asyncio.gather(*running, return_exceptions=True)

    async def _run(self) -> None:
        """Wait until the bot is ready, then step every ``interval`` seconds over one session.

        A step starts ``interval`` seconds after the previous one started and at least 0.1 seconds
        after it ended, v3's pacing (``CourseMonitorService.kt:34-36``).
        """
        await self.bot.wait_until_ready()
        async with self.open_api() as api:
            watcher = Watcher(
                self.config,
                self.lang,
                self.registrations,
                api.course,
                self._post,
                self.now,
                self.clock,
            )
            while True:
                started = self.clock()
                await watcher.step()
                elapsed = self.clock() - started
                await self.sleep(max(MIN_PAUSE, self.config.interval - elapsed))

    def _post(self, channel_id: int, post: Post) -> None:
        """Start a post to a channel, which holds up no step: v3 queued its posts too."""
        task = asyncio.create_task(self._send(channel_id, post), name="NtustCourseWatch post")
        self.posting.add(task)
        task.add_done_callback(self.posting.discard)

    async def _send(self, channel_id: int, post: Post) -> None:
        """Post through a partial messageable, logging what fails, since nothing awaits it."""
        try:
            await self._deliver(channel_id, post)
        except Exception:
            logger.exception("NtustCourseWatch: posting to channel %d failed", channel_id)

    async def _deliver(self, channel_id: int, post: Post) -> None:
        """Send ``post``, pinging its members only, to any kind of channel, cached or not.

        v3 cast the channel to a text channel, which threw for threads, announcement and voice
        channels and stopped its loop. A channel that Discord no longer knows has its
        registrations forgotten; another refusal is logged once per kind and episode.
        """
        channel = self.bot.get_partial_messageable(channel_id)
        failures = self.posts.setdefault(channel_id, Failures())
        try:
            await channel.send(content=post.content, allowed_mentions=_mentions(post.users))
        except discord.NotFound:
            self.posts.pop(channel_id, None)
            if await self.registrations.forget(channel_id):  # once for an alert's several posts
                logger.info(
                    "NtustCourseWatch: channel %d is gone; its registrations were forgotten",
                    channel_id,
                )
            return
        except POST_ERRORS as error:
            kind = error.status if isinstance(error, discord.HTTPException) else type(error)
            logger.log(
                logging.WARNING if failures.fail(kind) else logging.DEBUG,
                "NtustCourseWatch: channel %d refused an alert: %s",
                channel_id,
                describe(error),
            )
            return
        if failed := failures.succeed():
            logger.info(
                "NtustCourseWatch: channel %d takes the alerts again after %d refusals",
                channel_id,
                failed,
            )
        logger.debug("NtustCourseWatch: posted an alert to channel %d", channel_id)

    def command(self, name: str) -> app_commands.Command[Any, ..., None]:
        """Build v3's command ``name``, described from ``register.yaml``, for every member.

        A guild command, as in v3, without default permissions; the command tree defers it
        ephemerally, as v3's core did. The names stay v3's in every locale; ``id`` is the option
        of ``course-add`` and ``course-remove``, whose parameter is ``code``.
        """
        lang, spec = self.lang, COMMANDS[name]
        names = lang.command(name, f"{spec.key}.name")
        description = lang.command(spec.description, f"{spec.key}.description")
        if spec.option is None:
            return app_commands.Command(
                name=names, description=description, callback=self.list_courses
            )
        command: app_commands.Command[Any, ..., None] = app_commands.Command(
            name=names,
            description=description,
            callback=self.add_course if name == "course-add" else self.remove_course,
        )
        app_commands.rename(code=lang.command("id", f"{spec.key}.options.id.name"))(command)
        app_commands.describe(code=lang.command(spec.option, f"{spec.key}.options.id.description"))(
            command
        )
        return command

    async def add_course(self, interaction: discord.Interaction, code: str) -> None:
        """``/course-add``: register the member for a course in the command's channel.

        v3 stored the code as typed and the member as often as they ran the command; the code is
        read as NTUST writes it, and a member is registered once.
        """
        course = course_code(code)
        if course is None:
            await self._reply(interaction, "invalid-code")
            return
        await self.registrations.add(course, _channel(interaction), interaction.user.id)
        await self._reply(interaction, "registered")

    async def remove_course(self, interaction: discord.Interaction, code: str) -> None:
        """``/course-remove``: unregister the member from a course in the command's channel.

        v3 removed the channel's whole entry for the course, unregistering every member there. As
        in v3, the reply is the same when the member was not registered.
        """
        course = course_code(code)
        if course is None:
            await self._reply(interaction, "invalid-code")
            return
        await self.registrations.remove(course, _channel(interaction), interaction.user.id)
        await self._reply(interaction, "unregistered")

    async def list_courses(self, interaction: discord.Interaction) -> None:
        """``/course-list``: the member's courses in the command's channel, sorted.

        v3 matched the member's ID as a substring of each registered one and listed duplicates.
        """
        registered = await self.registrations.load()
        channel, user = _channel(interaction), interaction.user.id
        codes = sorted(
            code for code, channels in registered.items() if user in channels.get(channel, ())
        )
        content = course_list(self.lang, interaction.locale.value, codes)
        await interaction.edit_original_response(content=content)

    async def _reply(self, interaction: discord.Interaction, key: str) -> None:
        """Edit the command tree's ephemeral deferral into the reply ``key``, as v3 did.

        The reply is in the member's locale, else in en-US: v3's English.
        """
        content = text(self.lang, f"reply.{key}", interaction.locale.value)
        await interaction.edit_original_response(content=content)


def _ended(task: asyncio.Task[None]) -> None:
    """Log the error that ended the loop: nothing awaits it until the plugin unloads."""
    if not task.cancelled() and (error := task.exception()) is not None:
        logger.error(
            "NtustCourseWatch: the loop stopped, so no course is checked until the plugin reloads",
            exc_info=error,
        )


def _mentions(users: tuple[int, ...]) -> discord.AllowedMentions:
    """The members whom a post may ping, and nobody else: no roles, no ``@everyone``."""
    members = [discord.Object(user) for user in users] if users else False
    return discord.AllowedMentions(everyone=False, users=members, roles=False, replied_user=False)


def _channel(interaction: discord.Interaction) -> int:
    """The command's channel, which Discord sends with every command in a guild."""
    return interaction.channel_id or 0
