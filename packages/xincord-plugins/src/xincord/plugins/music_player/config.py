"""The plugin's ``config.yaml``: the Lavalink node, the player, the errors and the emojis.

Other keys (``engines.spotify``: the node's config holds it) are not fields: the core warns about
each.
"""

from typing import Annotated

from pydantic import ConfigDict, Field, StringConstraints

from xincord.core.config import Model

TIMEOUT_MAX = 2_147_483_647  # a 32-bit integer
# An application emoji's name, as Discord takes it: 2 to 32 letters, digits and underscores.
type EmojiName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_]{2,32}$")]


class Node(Model):
    """The Lavalink node: compose's ``lavalink`` service by default.

    The password is ``LAVALINK_PASSWORD`` of the ``.env`` file next to ``compose.yaml``; it has no
    default, and errors never show the input, which can be the password.
    """

    model_config = ConfigDict(hide_input_in_errors=True)

    host: Annotated[str, StringConstraints(min_length=1, max_length=253)] = "lavalink"
    port: Annotated[int, Field(ge=1, le=65535)] = 2333
    # A string, so that YAML never turns a number into another password; not blank.
    password: Annotated[str, Field(strict=True), StringConstraints(pattern=r"\S", max_length=512)]


class Player(Model):
    """The ``player`` keys."""

    default_volume: Annotated[int, Field(ge=0, le=100)] = 40
    # Milliseconds with no song playing before the bot leaves.
    auto_leave_timeout: Annotated[int, Field(ge=0, le=TIMEOUT_MAX)] = 600_000


class Messages(Model):
    """``messages.show_detailed_errors``."""

    show_detailed_errors: bool = True


class Emojis(Model):
    """The names of the application's emojis: nine for the panels and four for the buttons."""

    progress_white_start: EmojiName = "music_player__line_white_start"
    progress_white_full: EmojiName = "music_player__line_white_full"
    progress_white_end: EmojiName = "music_player__line_white_end"
    progress_black: EmojiName = "music_player__line_black"
    progress_black_end: EmojiName = "music_player__line_black_end"
    media_play: EmojiName = "music_player__media_play"
    media_pause: EmojiName = "music_player__media_pause"
    media_ordered: EmojiName = "music_player__media_ordered"
    media_repeat_once: EmojiName = "music_player__media_repeat_once"
    media_previous: EmojiName = "music_player__media_previous"
    media_pause_resume: EmojiName = "music_player__media_pause_resume"
    media_next: EmojiName = "music_player__media_next"
    media_disconnect: EmojiName = "music_player__media_disconnect"


class Config(Model):
    """``plugins/MusicPlayer/config.yaml``; the bundled ``config.yaml`` holds the same defaults.

    ``lavalink`` is required: the bundled file leaves its password empty, so the plugin waits for
    the operator. The core config's ``plugins`` list enables it; an ``enabled`` key only warns.
    """

    model_config = ConfigDict(hide_input_in_errors=True)

    lavalink: Node
    player: Player = Player()
    messages: Messages = Messages()
    emojis: Emojis = Emojis()
