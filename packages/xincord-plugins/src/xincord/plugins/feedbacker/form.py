"""The stars of a form: v3's star text and the star count that an ID carries.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/Feedbacker.kt:139-145
"""

MAX_STARS = 5  # v3's five star buttons


def stars(count: int) -> str:
    """Return v3's ``%fb_stars%`` for ``count`` stars of five."""
    raise NotImplementedError


def star_count(text: str) -> int:
    """Read the star count of an ID.

    Raises:
        ValueError: ``text`` is not a whole number from 0 to 5.
    """
    raise NotImplementedError
