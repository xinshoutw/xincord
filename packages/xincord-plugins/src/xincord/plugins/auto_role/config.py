"""The plugin's ``config.yaml``."""

from typing import Annotated

from pydantic import Field, PositiveInt

from xincord.core.config import Model


class GuildRoles(Model):
    """A guild and the roles that its new members get, validated as in v3."""

    guild_id: PositiveInt
    # Any integers, as v3's List<Long>: an ID that names no role is skipped at the join.
    role_ids: Annotated[tuple[int, ...], Field(min_length=1)]


class Config(Model):
    """``plugins/AutoRole/config.yaml``; the bundled ``config.yaml`` lists no guilds.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin.
    """

    guilds: tuple[GuildRoles, ...]  # required, as in v3

    def roles_by_guild(self) -> dict[int, tuple[int, ...]]:
        """Map each guild ID to its role IDs; a guild listed twice keeps its last entry (v3)."""
        return {entry.guild_id: entry.role_ids for entry in self.guilds}
