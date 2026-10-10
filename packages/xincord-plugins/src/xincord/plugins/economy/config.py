"""The plugin's ``config.yaml``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/config/ConfigSerializer.kt:6-42
"""

from typing import Annotated

from pydantic import Field

from xincord.core.config import Model

# v3's range for the number of board rows.
BOARD_MIN = 1
BOARD_MAX = 25


class Config(Model):
    """``plugins/Economy/config.yaml``: the administrators and the length of the boards.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin. v3's Google
    Sheets keys (``client_id``, ``client_secret``, ``port`` and ``sheet_*``) served the dead Sheets
    storage and only warn as unknown keys.
    """

    # The users who change wallets and see the boards and other users' wallets, in every guild.
    # v3 refused an empty list, so there is no default: the bundled file leaves it empty for the
    # operator, and the plugin does not load until it names someone.
    admin_id: Annotated[tuple[int, ...], Field(min_length=1)]
    board_user_show_limit: Annotated[int, Field(ge=BOARD_MIN, le=BOARD_MAX)] = 10
