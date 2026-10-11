"""The plugin's ``config.yaml``."""

from typing import Annotated

from pydantic import Field, PositiveInt

from xincord.core.config import Model


class GuildRoles(Model):
    """A guild and the roles that its new members get."""

    guild_id: PositiveInt
    # Any integers: an ID that names no role is skipped at the join.
    role_ids: Annotated[tuple[int, ...], Field(min_length=1)]


class Config(Model):
    """``plugins/AutoRole/config.yaml``; the bundled ``config.yaml`` lists no guilds.

    The core config's ``plugins`` list enables the plugin; an ``enabled`` key here only warns.
    """

    guilds: tuple[GuildRoles, ...]  # required

    def roles_by_guild(self) -> dict[int, tuple[int, ...]]:
        """Map each guild ID to its role IDs; a guild listed twice keeps its last entry."""
        return {entry.guild_id: entry.role_ids for entry in self.guilds}
