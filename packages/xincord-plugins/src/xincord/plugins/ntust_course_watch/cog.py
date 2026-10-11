"""The plugin's cog: the commands.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/Event.kt:14-61
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/NtustCourse.kt:15-142
    XsDiscordBotKt@3a59607:Plugins/NtustCourse/src/main/kotlin/ntustcourse/command/Register.kt:12-28
"""

from typing import TYPE_CHECKING, Any, NamedTuple

from discord.ext import commands

from .store import Registrations

if TYPE_CHECKING:
    import discord
    from discord import app_commands

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
        """Build v3's command ``name``."""
        raise NotImplementedError

    async def add_course(self, interaction: discord.Interaction, code: str) -> None:
        """``/course-add``: register the member for a course in the command's channel."""
        raise NotImplementedError

    async def remove_course(self, interaction: discord.Interaction, code: str) -> None:
        """``/course-remove``: unregister the member from a course in the command's channel."""
        raise NotImplementedError

    async def list_courses(self, interaction: discord.Interaction) -> None:
        """``/course-list``: the member's courses in the command's channel."""
        raise NotImplementedError
