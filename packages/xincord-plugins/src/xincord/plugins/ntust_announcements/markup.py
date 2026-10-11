"""An HTML tree over the standard library's parser, with CSS-like selectors and a text reader.

NTUST's pages are well formed, so this tree follows HTML only where pages may leave things out: void
elements, raw text, the end tags that HTML lets pages omit in tables and lists, and the table bodies
that HTML5 parsers add.
"""

import html
import re
import unicodedata
from dataclasses import dataclass, field
from functools import cache
from html.parser import HTMLParser
from typing import override

# Elements that have no content and no end tag.
VOID = frozenset(
    {
        "area",
        "base",
        "basefont",
        "bgsound",
        "br",
        "col",
        "embed",
        "frame",
        "hr",
        "img",
        "input",
        "keygen",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
# Elements whose content html.parser hands over unparsed: data, not text.
RAW_TEXT = frozenset({"script", "style", "xmp", "iframe", "noembed", "noframes"})
# The block elements, which the text separates from their neighbors with a space.
BLOCKS = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "body",
        "canvas",
        "caption",
        "center",
        "col",
        "colgroup",
        "dd",
        "del",
        "details",
        "dir",
        "div",
        "dl",
        "dt",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "frameset",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "head",
        "header",
        "hgroup",
        "hr",
        "html",
        "ins",
        "li",
        "main",
        "menu",
        "nav",
        "noscript",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
        "video",
    }
)
SECTIONS = frozenset({"tbody", "thead", "tfoot"})
TABLE_PARTS = frozenset({"table", "caption", "tr", "td", "th"}) | SECTIONS
# What a start tag closes when it is still open (HTML's optional end tags), and where the search
# for it stops.
IMPLIED: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "li": (frozenset({"li"}), frozenset({"ul", "ol", "table"})),
    "dt": (frozenset({"dt", "dd"}), frozenset({"dl", "table"})),
    "dd": (frozenset({"dt", "dd"}), frozenset({"dl", "table"})),
    "tr": (frozenset({"tr", "td", "th"}), frozenset({"table"}) | SECTIONS),
    "td": (frozenset({"td", "th"}), frozenset({"tr", "table"})),
    "th": (frozenset({"td", "th"}), frozenset({"tr", "table"})),
    **dict.fromkeys(SECTIONS, (SECTIONS | {"tr", "td", "th"}, frozenset({"table"}))),
}
# Start tags that close an open paragraph, and what stops the search for it (HTML's button scope).
CLOSES_PARAGRAPH = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "center",
        "dd",
        "details",
        "dir",
        "div",
        "dl",
        "dt",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hgroup",
        "hr",
        "li",
        "main",
        "menu",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "ul",
    }
)
PARAGRAPH_SCOPE = frozenset({"button", "table", "td", "th", "caption", "template", "object"})
# What stops the search for the element that an end tag closes: an end tag in a table cell closes
# nothing outside it, and a table's own end tags nothing outside the table.
CELL_SCOPE = frozenset({"table", "td", "th", "caption", "template"})
TABLE_SCOPE = frozenset({"table"})
# The text: the whitespace it collapses (with the no-break space) and the characters it drops.
WHITESPACE = frozenset(" \t\n\f\r\xa0")
INVISIBLE = frozenset("\u200b\xad")
# What the text is trimmed of: every character up to U+0020.
TEXT_TRIM = "".join(chr(code) for code in range(0x21))
# What separates classes: Unicode spaces but the no-break ones, and ASCII controls.
CLASS_SEPARATOR = re.compile(
    "["
    + "".join(
        re.escape(chr(code))
        for code in range(0x3001)
        if chr(code) in "\t\n\x0b\f\r\x1c\x1d\x1e\x1f"
        or (
            unicodedata.category(chr(code)) in {"Zs", "Zl", "Zp"}
            and chr(code) not in "\xa0\u2007\u202f"
        )
    )
    + "]+"
)
COMPOUND = re.compile(r"([A-Za-z][A-Za-z0-9-]*)?((?:[#.][A-Za-z0-9_-]+)*)")
PART = re.compile(r"([#.])([A-Za-z0-9_-]+)")


def _children() -> list[Element | str]:
    return []


def _attributes() -> dict[str, str | None]:
    return {}


@dataclass(frozen=True)
class Compound:
    """One step of a selector: a tag, IDs and classes, each optional."""

    tag: str
    ids: tuple[str, ...]
    classes: frozenset[str]  # in lower case: classes compare without case

    def matches(self, element: Element) -> bool:
        """Whether ``element`` has the tag, the IDs and every class."""
        return (
            (not self.tag or element.tag == self.tag)
            and all(element.attr("id") == wanted for wanted in self.ids)
            and self.classes <= element.classes()
        )


@cache
def _compile(selector: str) -> tuple[Compound, ...]:
    """The compound selectors of ``selector``, joined by descendant combinators.

    Raises:
        ValueError: The selector uses more than tags, IDs, classes and descendants.
    """
    compounds: list[Compound] = []
    for part in selector.split():
        match = COMPOUND.fullmatch(part)
        if match is None:
            msg = f"unsupported selector: {selector}"
            raise ValueError(msg)
        found = PART.findall(match[2])
        compounds.append(
            Compound(
                (match[1] or "").lower(),
                tuple(name for kind, name in found if kind == "#"),
                frozenset(name.lower() for kind, name in found if kind == "."),
            )
        )
    if not compounds:
        msg = f"unsupported selector: {selector}"
        raise ValueError(msg)
    return tuple(compounds)


@dataclass(eq=False)
class Element:
    """An element of a parsed page, or the document itself (tag ``#document``)."""

    tag: str
    attrs: dict[str, str | None] = field(default_factory=_attributes)
    children: list[Element | str] = field(default_factory=_children)
    parent: Element | None = None

    def attr(self, name: str) -> str:
        """The attribute's value, or an empty text when it is missing."""
        return self.attrs.get(name) or ""

    def classes(self) -> frozenset[str]:
        """The element's classes, in lower case, split at ``CLASS_SEPARATOR``.

        It leaves out the no-break spaces, which Python's ``str.split`` takes.
        """
        return frozenset(part for part in CLASS_SEPARATOR.split(self.attr("class").lower()) if part)

    def select(self, selector: str) -> list[Element]:
        """The element and its descendants that match ``selector``, in document order.

        Tags, ``#id`` and ``.class`` (without case), joined by descendant
        combinators, the element itself counting as a match and as an ancestor.
        """
        compounds = _compile(selector)
        return [element for element in self._elements() if self._matches(element, compounds)]

    def select_first(self, selector: str) -> Element | None:
        """The first element that :meth:`select` gives, if any."""
        found = self.select(selector)
        return found[0] if found else None

    def _elements(self) -> list[Element]:
        """The element and its descendants, in document order."""
        found: list[Element] = []
        pending: list[Element] = [self]
        while pending:
            element = pending.pop()
            found.append(element)
            pending.extend(
                reversed([child for child in element.children if isinstance(child, Element)])
            )
        return found

    def _matches(self, element: Element, compounds: tuple[Compound, ...]) -> bool:
        """Whether ``element`` matches the compounds, its ancestors up to this element included.

        Matching each step with the nearest ancestor that fits is enough for descendant
        combinators: a nearer one leaves more ancestors for the steps before it.
        """
        *ancestors, last = compounds
        if not last.matches(element):
            return False
        current = element
        while ancestors and current is not self and current.parent is not None:
            current = current.parent
            if ancestors[-1].matches(current):
                ancestors.pop()
        return not ancestors

    def text(self) -> str:
        """The element's text.

        Runs of whitespace (the no-break space included) become one space, U+200B and U+00AD go,
        ``br`` and block elements separate their neighbors with a space, raw text (scripts,
        styles) is left out, and the result is trimmed of ``TEXT_TRIM``. ``pre`` gets no special
        treatment: titles hold none.
        """
        accumulated: list[str] = []
        _accumulate(self, accumulated)
        return "".join(accumulated).strip(TEXT_TRIM)

    def outer_html(self) -> str:
        """The element serialized as HTML: attributes in their order, comments left out."""
        out: list[str] = []
        _serialize(self, out)
        return "".join(out)


def _ends_with_space(accumulated: list[str]) -> bool:
    return bool(accumulated) and accumulated[-1] == " "


def _accumulate(root: Element, accumulated: list[str]) -> None:
    """Add the text of ``root``'s children to ``accumulated``, one character a piece.

    ``head`` adds a space before a block or a ``br`` that follows
    text, ``tail`` after a block that text or an inline element follows. The walk keeps its own
    stack, so that no nesting depth exhausts Python's recursion limit.
    """
    if root.tag in RAW_TEXT:
        return
    # (node, its next sibling, whether its children are done)
    pending: list[tuple[Element | str, Element | str | None, bool]] = []
    _push_children(root, pending)
    while pending:
        node, following, done = pending.pop()
        if isinstance(node, str):
            _append_collapsed(node, accumulated)
        elif done:
            if (
                node.tag in BLOCKS
                and following is not None
                and (isinstance(following, str) or following.tag not in BLOCKS)
                and not _ends_with_space(accumulated)
            ):
                accumulated.append(" ")
        else:
            separates = node.tag in BLOCKS or node.tag == "br"
            if accumulated and separates and not _ends_with_space(accumulated):
                accumulated.append(" ")
            pending.append((node, following, True))
            if node.tag not in RAW_TEXT:
                _push_children(node, pending)


def _push_children(
    element: Element, pending: list[tuple[Element | str, Element | str | None, bool]]
) -> None:
    """Push ``element``'s children, the first on top, each with its next sibling."""
    children = element.children
    for index in reversed(range(len(children))):
        following = children[index + 1] if index + 1 < len(children) else None
        pending.append((children[index], following, False))


def _append_collapsed(text: str, accumulated: list[str]) -> None:
    """Append ``text`` with its whitespace collapsed, and none leading after a space."""
    strip_leading = _ends_with_space(accumulated)
    last_was_white = False
    reached_non_white = False
    for character in text:
        if character in WHITESPACE:
            if (strip_leading and not reached_non_white) or last_was_white:
                continue
            accumulated.append(" ")
            last_was_white = True
        elif character not in INVISIBLE:
            accumulated.append(character)
            last_was_white = False
            reached_non_white = True


def _serialize(root: Element, out: list[str]) -> None:
    """Write ``root`` as HTML into ``out``, with a stack of its own instead of recursion."""
    # (a node, or an end tag to write as it is; whether a text is raw)
    pending: list[tuple[Element | str, bool]] = [(root, False)]
    while pending:
        node, raw = pending.pop()
        if isinstance(node, str):
            out.append(node if raw else html.escape(node, quote=False))
            continue
        attributes = "".join(
            f" {name}" if value is None else f' {name}="{html.escape(value)}"'
            for name, value in node.attrs.items()
        )
        out.append(f"<{node.tag}{attributes}>")
        if node.tag in VOID:
            continue
        pending.append((f"</{node.tag}>", True))
        pending.extend((child, node.tag in RAW_TEXT) for child in reversed(node.children))


class _Builder(HTMLParser):
    """Builds the tree from html.parser's events."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.document = Element("#document")
        self.stack: list[Element] = [self.document]

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in IMPLIED:
            self._close_implied(*IMPLIED[tag])
        if tag in CLOSES_PARAGRAPH:
            self._close_implied(frozenset({"p"}), PARAGRAPH_SCOPE)
        if tag in {"tr", "td", "th"} and self.stack[-1].tag == "table":
            self._open("tbody", [])  # HTML5 parsers add the body of a table without one
        if tag in {"td", "th"} and self.stack[-1].tag in SECTIONS:
            self._open("tr", [])
        self._open(tag, attrs)
        if tag in VOID:
            self.stack.pop()

    @override
    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # HTML ignores the slash of a non-void start tag: <a href=x /> stays open.
        self.handle_starttag(tag, attrs)

    @override
    def handle_endtag(self, tag: str) -> None:
        scope = TABLE_SCOPE if tag in TABLE_PARTS else CELL_SCOPE
        for index in range(len(self.stack) - 1, 0, -1):
            current = self.stack[index].tag
            if current == tag:
                del self.stack[index:]
                return
            if current in scope:
                return

    @override
    def handle_data(self, data: str) -> None:
        children = self.stack[-1].children
        if children and isinstance(children[-1], str):
            children[-1] += data
        else:
            children.append(data)

    def _open(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes: dict[str, str | None] = {}
        for name, value in attrs:
            attributes.setdefault(name, value)  # the first of duplicate attributes wins
        parent = self.stack[-1]
        element = Element(tag, attributes, parent=parent)
        parent.children.append(element)
        self.stack.append(element)

    def _close_implied(self, closes: frozenset[str], scope: frozenset[str]) -> None:
        """Close the open elements in ``closes``, nearest first, until ``scope`` stops the search.

        Each search skips the elements in neither set: ``<li><span>`` then ``<li>`` closes both.
        """
        while True:
            for index in range(len(self.stack) - 1, 0, -1):
                current = self.stack[index].tag
                if current in scope:
                    return
                if current in closes:
                    del self.stack[index:]
                    break
            else:
                return


def parse(page: str) -> Element:
    """Parse ``page`` into a tree and return its document."""
    builder = _Builder()
    builder.feed(page)
    builder.close()
    return builder.document
