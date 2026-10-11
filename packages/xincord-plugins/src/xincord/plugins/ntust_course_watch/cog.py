"""The plugin's cog: the commands.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/Event.kt:14-61
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/NtustCourse.kt:15-142
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/command/Register.kt:12-28
"""

from typing import TYPE_CHECKING, Any, NamedTuple

import discord
from discord import app_commands
from discord.ext import commands

from .courses import course_code
from .store import Registrations
from .texts import course_list, text

if TYPE_CHECKING:
    from xincord.core.i18n import Lang
    from xincord.core.storage import Store

    from .config import Config


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


def _channel(interaction: discord.Interaction) -> int:
    """The command's channel, which Discord sends with every command in a guild."""
    return interaction.channel_id or 0
