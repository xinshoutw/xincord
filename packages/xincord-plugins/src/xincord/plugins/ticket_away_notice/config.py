"""The plugin's ``config.yaml``."""

from typing import Annotated

from pydantic import ConfigDict, Field, PositiveInt

from xincord.core.config import Model

DELAY_MAX = 2**63 - 1  # a 64-bit integer


class Config(Model):
    """``plugins/TicketAwayNotice/config.yaml``: the keys, none with a default.

    The core config's ``plugins`` list enables the plugin; an ``enabled`` key here only warns. The
    bundled file holds 0 for both IDs, so the plugin waits for the operator.
    """

    # An unquoted prefix such as 2024 is read as the text in the file, where YAML gives a
    # number; YAML 1.1 still reads no as a boolean and 007 as 7, which need quotes.
    model_config = ConfigDict(coerce_numbers_to_str=True)

    # Files hold unquoted 18-digit numbers; pydantic reads quoted ones too.
    guild_id: PositiveInt  # the guild whose new channels are watched
    user_id: PositiveInt  # the member whose status decides the notice: the shop's owner
    prefix: Annotated[tuple[str, ...], Field(min_length=1)]  # channel name prefixes
    delay_millis: Annotated[int, Field(ge=1, le=DELAY_MAX)]  # the wait before the notice

    def watches(self, guild_id: int, name: str) -> bool:
        """Whether a new channel named ``name`` in guild ``guild_id`` gets a notice.

        Only ``guild_id`` counts. The prefixes compare case-sensitively; an empty one matches every
        name.
        """
        return guild_id == self.guild_id and name.startswith(self.prefix)
