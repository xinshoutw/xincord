"""What a board's first page lists and what an article's page holds.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementParser.kt:104-236
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/util/HtmlMinifier.kt:18-51
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/util/UrlUtils.kt:37-74
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Board


@dataclass(frozen=True)
class Link:
    """An entry of a board's page: v3's ``AnnouncementLink``, its stored item."""

    board: str  # the board's name, v3's ``type``
    url: str  # the announcement's identity
    title: str


def board_links(html: str, board: Board, page_url: str) -> list[Link]:
    """The entries that ``board``'s first page lists, in page order."""
    raise NotImplementedError


def complete_url(href: str, page_url: str) -> str:
    """A link's URL, from its ``href`` on the page at ``page_url``."""
    raise NotImplementedError


def is_article(url: str) -> bool:
    """Whether ``url`` is an NTUST article, whose content Gemini converts."""
    raise NotImplementedError


def article_html(html: str) -> str | None:
    """The minified HTML of an article page's content container, if it has one."""
    raise NotImplementedError


def minify(html: str) -> str:
    """``html`` without comments and the whitespace that does not show, as v3's minifier."""
    raise NotImplementedError


def trim(text: str) -> str:
    """``text`` without the leading and trailing characters that Kotlin's ``trim()`` removes."""
    raise NotImplementedError
