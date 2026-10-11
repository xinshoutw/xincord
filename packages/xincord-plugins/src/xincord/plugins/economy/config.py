"""The plugin's ``config.yaml``."""

from typing import Annotated

from pydantic import Field

from xincord.core.config import Model

# The range for the number of board rows.
BOARD_MIN = 1
BOARD_MAX = 25


class Config(Model):
    """``plugins/Economy/config.yaml``: the administrators and the length of the boards.

    The core config's ``plugins`` list enables the plugin; an ``enabled`` key here only warns, as do
    other unknown keys.
    """

    # The users who change wallets and see the boards and other users' wallets, in every guild.
    # An empty list is refused, so there is no default: the bundled file leaves it empty for the
    # operator, and the plugin does not load until it names someone.
    admin_id: Annotated[tuple[int, ...], Field(min_length=1)]
    board_user_show_limit: Annotated[int, Field(ge=BOARD_MIN, le=BOARD_MAX)] = 10
