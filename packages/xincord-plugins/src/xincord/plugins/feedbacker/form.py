"""The stars of a form: v3's star text, the star count that an ID carries and the highlight.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/Feedbacker.kt:106-124
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/Feedbacker.kt:139-145
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord

MAX_STARS = 5  # v3's five star buttons
FULL, EMPTY = "★ ", "☆ "  # v3's stars, each followed by a space
# The counts an ID may carry, as v3's templates write them: v3's repeat threw outside 0 to 5.
COUNTS = {str(count): count for count in range(MAX_STARS + 1)}


def stars(count: int) -> str:
    """Return v3's ``%fb_stars%`` for ``count`` stars of five, trailing space included."""
    return FULL * count + EMPTY * (MAX_STARS - count)


def star_count(text: str) -> int:
    """Read the star count of an ID.

    Raises:
        ValueError: ``text`` is not a whole number from 0 to 5.
    """
    try:
        return COUNTS[text]
    except KeyError:
        msg = f"star count {text!r} is not a whole number from 0 to {MAX_STARS}"
        raise ValueError(msg) from None


def highlight(message: discord.Message, pressed: str) -> discord.ui.View | discord.ui.LayoutView:
    """Return the message's components with the pressed button primary and the others secondary."""
    raise NotImplementedError
