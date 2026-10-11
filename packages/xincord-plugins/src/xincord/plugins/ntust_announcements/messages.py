"""The Discord messages of an announcement: v3's header, split and title links.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/NtustManager.kt:97-183
"""

HEADER = chr(0xFF3F) * 15  # v3's 15 FULLWIDTH LOW LINEs before an announcement
MESSAGE_LIMIT = 2000  # Discord's limit for a message's content


def units(text: str) -> int:
    """The length of ``text`` in UTF-16 code units, as Kotlin's ``String.length`` counts it."""
    raise NotImplementedError


def split(content: str, limit: int) -> list[str]:
    """``content`` in parts of at most ``limit`` units, as v3's ``splitContentIntoSegments``."""
    raise NotImplementedError


def content_messages(content: str) -> list[str]:
    """The messages that post Gemini's ``content``, the header on the first."""
    raise NotImplementedError


def link_message(title: str, url: str) -> str:
    """The message that posts an announcement as its title, linked to ``url``."""
    raise NotImplementedError
