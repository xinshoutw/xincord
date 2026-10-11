"""The stars of a form: v3's star text, the star count that an ID carries and the highlight."""

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
    """Return the message's components with the pressed button primary and the others secondary.

    Only buttons with an ID change: link and premium buttons keep their style, and the message's
    other components stay (v3 rebuilt the action rows and dropped the rest). The view is a fresh
    copy, stopped so that discord.py never dispatches its presses: the core routes them.
    """
    view_type = discord.ui.LayoutView if message.flags.components_v2 else discord.ui.View
    view = view_type.from_message(message, timeout=None)
    for item in view.walk_children():
        if isinstance(item, discord.ui.Button) and item.custom_id is not None:
            pressed_now = item.custom_id == pressed
            item.style = (
                discord.ButtonStyle.primary if pressed_now else discord.ButtonStyle.secondary
            )
    view.stop()
    return view
