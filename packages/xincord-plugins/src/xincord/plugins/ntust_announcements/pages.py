"""What a board's first page lists and what an article's page holds."""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlsplit

from .config import Layout
from .markup import parse
from .strings import trim

if TYPE_CHECKING:
    from .config import Board
    from .markup import Element

# The Language Center's title link in each row (AnnouncementParser.kt:117-121).
TITLE_LINK = "div.d-item.d-title.col-sm-12 div.mbox div.d-txt div.mtitle a"
# v3's validateUrlType, a full match (UrlUtils.kt:56): what the model converts. v3's ".*" before the
# host's ".ntust.edu.tw" took any host; the host's characters stop at "/", "?" and "#" now.
ARTICLE = re.compile(r"https://[^/?#]*\.ntust\.edu\.tw/p/[0-9\-,r]+\.php.*")
# An article page's content: v3's container, else its fallback (AnnouncementParser.kt:227-229).
CONTAINERS = ("div#Dyn_2_3.M23", "div.M23")
SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
# v3's minifier, in order; Java's \s is ASCII (HtmlMinifier.kt:24-37).
MINIFY = (
    (re.compile(r"<!--[\s\S]*?-->", re.ASCII), ""),
    (re.compile(r">\s+<", re.ASCII), "><"),
    (re.compile(r"^\s+", re.ASCII | re.MULTILINE), ""),
    # v3's \s+$, which could start anywhere in a run of whitespace and backtrack through it (40,000
    # spaces: 5 s); a run is matched from its start only, which removes the same text.
    (re.compile(r"(?<!\s)\s+$", re.ASCII | re.MULTILINE), ""),
    (re.compile(r"\s{2,}", re.ASCII), " "),
    (re.compile(r"\n\s*\n", re.ASCII), "\n"),
)


@dataclass(frozen=True)
class Link:
    """An entry of a board's page: v3's ``AnnouncementLink``, its stored item."""

    board: str  # the board's name, v3's ``type``
    url: str  # the announcement's identity
    title: str


def board_links(html: str, board: Board, page_url: str) -> list[Link]:
    """The entries that ``board``'s first page lists, in page order (``parseAnnouncementList``).

    Student Affairs and Academic Affairs boards list their entries in the first
    ``table.listTB.table``, the title link in each body row's first or second cell (rows with
    fewer than two cells are skipped); Language Center boards in ``div.row.listBS`` rows. Rows
    without a link are skipped; titles are kept blank (a pass leaves such entries out). The
    ``title-prefix`` keeps the titles that start with it, for every layout.
    """
    document = parse(html)
    if board.layout is Layout.LANGUAGE_CENTER:
        anchors = [row.select_first(TITLE_LINK) for row in document.select("div.row.listBS")]
    else:
        anchors = _table_links(document, 0 if board.layout is Layout.STUDENT_AFFAIRS else 1)
    entries: list[Link] = []
    for anchor in anchors:
        if anchor is None:
            continue
        title = trim(anchor.text())
        if title.startswith(board.title_prefix):
            entries.append(Link(board.name, complete_url(anchor.attr("href"), page_url), title))
    return entries


def _table_links(document: Element, column: int) -> list[Element | None]:
    """The first link of each body row's cell ``column``, from the first list table."""
    table = document.select_first("table.listTB.table")
    if table is None:
        return []
    anchors: list[Element | None] = []
    for row in table.select("tbody tr"):
        cells = row.select("td")
        if len(cells) >= 2:  # noqa: PLR2004 - v3 skipped rows without a title and a date cell
            anchors.append(cells[column].select_first("a"))
    return anchors


def complete_url(href: str, page_url: str) -> str:
    """A link's URL, from its ``href`` on the page at ``page_url`` (the page after redirects).

    v3's ``constructCompleteUrl`` kept an ``https://`` link and gave a ``/`` path the page's
    host: both keep v3's exact strings, an announcement's identity. v3 also kept other links as
    written, which mangled ``//host/path`` and left relative paths relative: they resolve against
    the page now. Other schemes (``http:``, ``mailto:``) and blank links stay as written.
    """
    if href.startswith("https://") or not href.strip():
        return href
    page = urlsplit(page_url)
    if href.startswith("//"):
        return f"{page.scheme}:{href}"
    if href.startswith("/"):
        return f"{page.scheme}://{page.netloc}{href}"
    if SCHEME.match(href):
        return href
    return urljoin(page_url, href)


def is_article(url: str) -> bool:
    """Whether ``url`` is an NTUST article, whose content the model converts (``validateUrlType``).

    Other links, NTUST's files and PDFs included, are posted as their title.
    """
    return ARTICLE.fullmatch(url) is not None


def article_html(html: str) -> str | None:
    """The minified HTML of an article page's content container, if it has one.

    v3 sent jsoup's pretty-printed serialization of the container; this is the tree serialized,
    which reads the same to the model.
    """
    document = parse(html)
    for selector in CONTAINERS:
        if (container := document.select_first(selector)) is not None:
            return minify(container.outer_html())
    return None


def minify(html: str) -> str:
    """``html`` without comments and the whitespace that does not show, as v3's minifier.

    Line breaks become ``\\n`` first, as an HTML parser makes them, so that the line-based steps
    see the lines that Java's saw; a blank text is returned as it is, as in v3.
    """
    if not trim(html):
        return html
    text = html.replace("\r\n", "\n").replace("\r", "\n")
    for pattern, replacement in MINIFY:
        text = pattern.sub(replacement, text)
    return trim(text)
