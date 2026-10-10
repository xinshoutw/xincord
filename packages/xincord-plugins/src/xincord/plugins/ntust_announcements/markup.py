"""An HTML tree over the standard library's parser, read with v3's selectors and Ksoup's text().

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementParser.kt:108-236
"""

from dataclasses import dataclass, field


def _children() -> list[Element | str]:
    return []


@dataclass(eq=False)
class Element:
    """An element of a parsed page, or the document itself (tag ``#document``)."""

    tag: str
    attrs: dict[str, str | None] = field(default_factory=dict[str, str | None])
    children: list[Element | str] = field(default_factory=_children)
    parent: Element | None = None

    def attr(self, name: str) -> str:
        """The attribute's value, or an empty text when it is missing, as jsoup's ``attr``."""
        raise NotImplementedError

    def select(self, selector: str) -> list[Element]:
        """The element and its descendants that match ``selector``, in document order."""
        raise NotImplementedError

    def select_first(self, selector: str) -> Element | None:
        """The first element that :meth:`select` gives, if any."""
        raise NotImplementedError

    def text(self) -> str:
        """The element's text as jsoup's ``text()`` gives it: whitespace collapsed and trimmed."""
        raise NotImplementedError

    def outer_html(self) -> str:
        """The element serialized as HTML, comments left out."""
        raise NotImplementedError


def parse(html: str) -> Element:
    """Parse ``html`` into a tree and return its document."""
    raise NotImplementedError
