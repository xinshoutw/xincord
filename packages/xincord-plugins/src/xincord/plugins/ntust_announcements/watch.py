"""One board's passes: its new entries posted in page order, its posted list kept.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementScheduler.kt:155-256
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementParser.kt:61-102
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/NtustManager.kt:185-237
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from xincord.plugins.failures import Failures

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from .config import Board
    from .pages import Link
    from .store import Posted
    from .web import Page

type FetchPage = Callable[[str], Awaitable[Page]]
type Convert = Callable[[str, Link], Awaitable[str | None]]  # an article's HTML to Markdown
type Post = Callable[[int, str], Awaitable[object]]  # one message to a channel
type Sleep = Callable[[float], Awaitable[object]]


@dataclass
class Watcher:
    """One board and its effects: its pages, Gemini, its channel and its posted list."""

    board: Board
    page: FetchPage
    convert: Convert
    post: Post
    posted: Posted
    # Failure episodes: the board's page, its articles' pages, its posts and its document.
    pages: Failures = field(default_factory=Failures)
    articles: Failures = field(default_factory=Failures)
    posts: Failures = field(default_factory=Failures)
    document: Failures = field(default_factory=Failures)

    async def check(self) -> None:
        """One pass: post the page's entries that the board has not posted yet, in page order."""
        raise NotImplementedError

    async def run(self, interval: float, sleep: Sleep) -> None:
        """Pass at once, then ``interval`` seconds after each pass, until cancelled."""
        raise NotImplementedError
