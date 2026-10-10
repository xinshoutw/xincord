"""The builder's inputs as v3 checked them, and texts cut to Discord's limits.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:70-151
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:373-379
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:629-632
"""


def trim(text: str) -> str:
    """``text`` without leading and trailing whitespace, as Kotlin's ``String.trim()``."""
    raise NotImplementedError


def winner_count(text: str) -> int | None:
    """The winner count that ``text`` holds, from 1 to 50, or None."""
    raise NotImplementedError


def is_http_url(text: str) -> bool:
    """Whether ``text`` is an http or https URL with a host, as v3's check with Java's ``URI``."""
    raise NotImplementedError


def thumbnail(url: str) -> str | None:
    """The URL to show as a thumbnail, with its scheme in lower case, or None."""
    raise NotImplementedError


def clip(text: str, limit: int) -> str:
    """``text`` cut to ``limit`` UTF-16 code units with ``...``, as v3's ``clipFieldText``."""
    raise NotImplementedError
