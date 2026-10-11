"""What v3's parsers read from NTUST's pages: the boards' entries and the articles' content.

The pages are trimmed copies of NTUST's, fetched on 2026-10-11; the expected entries are in
golden.yaml.
"""

import time

import pytest

from plugin_fakes import FIXTURES, golden
from xincord.plugins.ntust_announcements.config import Board
from xincord.plugins.ntust_announcements.pages import (
    Link,
    article_html,
    board_links,
    complete_url,
    is_article,
    minify,
)
from xincord.plugins.ntust_announcements.strings import trim

PAGES = FIXTURES / "plugins" / "ntust_announcements"
GOLDEN = golden("ntust_announcements")
STUDENT = "https://student.ntust.edu.tw/p/403-1053-1436-1.php"
NBSP = chr(0xA0)
IDEOGRAPHIC_SPACE = chr(0x3000)
NEXT_LINE = chr(0x85)


def page(name: str) -> str:
    """A fixture page's HTML."""
    return (PAGES / name).read_text(encoding="utf-8")


def board(name: str, layout: str, url: str = STUDENT, title_prefix: str = "") -> Board:
    """A board of the config."""
    return Board.model_validate(
        {
            "name": name,
            "url": url,
            "layout": layout,
            "channel-id": 1,
            "title-prefix": title_prefix,
        }
    )


def expected(fixture: str) -> list[Link]:
    """The golden entries of a fixture page."""
    return [Link(item["type"], item["url"], item["title"]) for item in GOLDEN["entries"][fixture]]


def test_student_affairs_board() -> None:
    """Requirement: Board pages list their announcements."""
    dormitory = board("STUDENT_DORMITORY", "student-affairs")

    links = board_links(page("student-dormitory.html"), dormitory, STUDENT)

    # The page's top menu links an article too; only the table's rows count.
    assert links == expected("student-dormitory.html")
    assert links[-1].url.startswith("https://docs.google.com/")


def test_academic_affairs_board() -> None:
    """Requirement: Board pages list their announcements."""
    url = "https://www.academic.ntust.edu.tw/p/403-1048-1416-1.php"
    course = board("ACADEMIC_COURSE", "academic-affairs", url)

    assert board_links(page("academic-course.html"), course, url) == expected(
        "academic-course.html"
    )


def test_language_center_board() -> None:
    """Requirement: Board pages list their announcements."""
    url = "https://lc.ntust.edu.tw/p/403-1070-1626-1.php"
    recruitment = board("LANGUAGE_CENTER_RECRUITMENT", "language-center", url)

    assert board_links(page("language-center-recruitment.html"), recruitment, url) == expected(
        "language-center-recruitment.html"
    )


def test_title_prefix() -> None:
    """Requirement: Board pages list their announcements."""
    url = "https://student.ntust.edu.tw/p/403-1053-1435-1.php"
    html = page("student-main-office.html")
    office = board("STUDENT_MAIN_OFFICE", "student-affairs", url, GOLDEN["title_prefix"])

    assert board_links(html, office, url) == expected("student-main-office.html")
    # Without the prefix, the page's three rows.
    assert len(board_links(html, board("STUDENT_MAIN_OFFICE", "student-affairs", url), url)) == 3


@pytest.mark.parametrize(
    ("href", "page_url", "url"),
    [
        pytest.param(
            "https://student.ntust.edu.tw/p/406-1053-152183,r1436.php?Lang=zh-tw",
            STUDENT,
            "https://student.ntust.edu.tw/p/406-1053-152183,r1436.php?Lang=zh-tw",
            id="https as written",
        ),
        pytest.param(
            "/p/404-1048-78935.php?Lang=zh-tw",
            "https://www.academic.ntust.edu.tw/p/403-1048-1416-1.php",
            "https://www.academic.ntust.edu.tw/p/404-1048-78935.php?Lang=zh-tw",
            id="path",
        ),
        pytest.param(
            "/p/x.php", "http://127.0.0.1:8080/p/1.php", "http://127.0.0.1:8080/p/x.php", id="port"
        ),
        pytest.param("//www.example.com/x", STUDENT, "https://www.example.com/x", id="no scheme"),
        pytest.param(
            "406-1053-1,r1436.php",
            STUDENT,
            "https://student.ntust.edu.tw/p/406-1053-1,r1436.php",
            id="relative",
        ),
        pytest.param(
            "http://www.ald.org.tw/OnePage.aspx?mid=2&id=74",
            STUDENT,
            "http://www.ald.org.tw/OnePage.aspx?mid=2&id=74",
            id="http as written",
        ),
        pytest.param("mailto:office@example.com", STUDENT, "mailto:office@example.com", id="mail"),
    ],
)
def test_links(href: str, page_url: str, url: str) -> None:
    """Requirement: Board pages list their announcements."""
    assert complete_url(href, page_url) == url


def test_rows() -> None:
    """Requirement: Board pages list their announcements."""
    html = (
        '<table class="listTB table"><thead><tr><th>Title</th><th>Date</th></tr></thead><tbody>'
        '<tr><td><a href="/p/1.php">One</a></td><td>2026-10-01</td></tr>'
        '<tr><td><a href="2.php"> </a></td><td>2026-10-02</td></tr>'
        "<tr><td>No link</td><td>2026-10-03</td></tr>"
        '<tr><td><a href="/p/4.php">One cell</a></td></tr>'
        '<tr><td>2026-10-05</td><td><a href="/p/5.php">Five</a></td></tr>'
        "</tbody></table>"
    )

    # Blank titles stay (a pass leaves them out); rows without a link or a second cell do not.
    assert board_links(html, board("S", "student-affairs"), STUDENT) == [
        Link("S", "https://student.ntust.edu.tw/p/1.php", "One"),
        Link("S", "https://student.ntust.edu.tw/p/2.php", ""),
    ]
    assert board_links(html, board("A", "academic-affairs"), STUDENT) == [
        Link("A", "https://student.ntust.edu.tw/p/5.php", "Five"),
    ]


def test_no_list() -> None:
    """Requirement: Board pages list their announcements."""
    recruitment = page("language-center-recruitment.html")
    dormitory = page("student-dormitory.html")
    rows = (
        '<div class="row listBS"><div class="mtitle"><a href="/p/1.php">Elsewhere</a></div></div>'
    )

    assert board_links(recruitment, board("S", "student-affairs"), STUDENT) == []
    assert board_links(dormitory, board("L", "language-center"), STUDENT) == []
    assert board_links(rows, board("L", "language-center"), STUDENT) == []


@pytest.mark.parametrize(
    ("text", "trimmed"),
    [
        pytest.param(f" {IDEOGRAPHIC_SPACE}{NBSP}One two\t\n", "One two", id="Unicode spaces"),
        pytest.param(f"{NEXT_LINE}One{NEXT_LINE}", f"{NEXT_LINE}One{NEXT_LINE}", id="next line"),
        pytest.param("   ", "", id="blank"),
    ],
)
def test_trim(text: str, trimmed: str) -> None:
    """Requirement: Board pages list their announcements."""
    # Kotlin's trim() removes what Char.isWhitespace() accepts, which leaves U+0085 out.
    assert trim(text) == trimmed


def test_container() -> None:
    """Requirement: Article pages give their content as minified HTML."""
    html = article_html(page("student-article.html"))
    assert html is not None

    # The class attribute's two spaces collapse too, as v3's minifier did to the whole text.
    assert html.startswith(
        '<div id="Dyn_2_3" class="M23 "><div class="module module-detail md_style1">'
        '<div class="module-inner"><section class="mb"><div class="mpgtitle"><h2 class="hdline">'
    )
    assert html.endswith("</section></div></div></div>")
    assert "font-family" in html  # the article's own style element stays
    assert "#0000</p>" in html
    assert "<!--" not in html
    assert "\t" not in html
    assert "  " not in html
    assert "trimmed copy" not in html  # the page's comment, outside the container


def test_fallback_container() -> None:
    """Requirement: Article pages give their content as minified HTML."""
    html = article_html(page("academic-article.html"))
    assert html is not None

    assert html.startswith('<div id="Dyn_2_2" class="M23 "><div class="module module-detail')
    assert html.endswith("</div>")


def test_preferred_container() -> None:
    """Requirement: Article pages give their content as minified HTML."""
    html = '<div class="M23">first</div><div id="Dyn_2_3" class="M23">second</div>'

    assert article_html(html) == '<div id="Dyn_2_3" class="M23">second</div>'


@pytest.mark.parametrize(
    "html",
    [
        pytest.param('<div class="M24">x</div>', id="another class"),
        pytest.param('<div id="Dyn_2_3">x</div>', id="ID without the class"),
        pytest.param('<p class="M23">x</p>', id="not a division"),
    ],
)
def test_no_container(html: str) -> None:
    """Requirement: Article pages give their content as minified HTML."""
    assert article_html(html) is None


@pytest.mark.parametrize(
    ("html", "minified"),
    [
        pytest.param("<p>a<!-- one\n two --></p><!---->", "<p>a</p>", id="comments"),
        pytest.param("<div>\n  <p>a</p>\n</div>", "<div><p>a</p></div>", id="between tags"),
        pytest.param("<p>\n   text   \n</p>", "<p>\ntext\n</p>", id="line edges"),
        pytest.param("<p>a \t b</p>", "<p>a b</p>", id="runs"),
        pytest.param("<p>a\n\n\nb</p>", "<p>a\nb</p>", id="empty lines"),
        pytest.param("<p>a\r   b</p>", "<p>a\nb</p>", id="carriage return"),
        pytest.param(
            f"<p>a{NBSP}{NBSP}b{IDEOGRAPHIC_SPACE}{IDEOGRAPHIC_SPACE}c</p>",
            f"<p>a{NBSP}{NBSP}b{IDEOGRAPHIC_SPACE}{IDEOGRAPHIC_SPACE}c</p>",
            id="Unicode spaces stay",
        ),
        pytest.param("  <p>a</p>  ", "<p>a</p>", id="trimmed"),
        pytest.param(" \n ", " \n ", id="blank as is"),
    ],
)
def test_minify(html: str, minified: str) -> None:
    """Requirement: Article pages give their content as minified HTML."""
    assert minify(html) == minified


@pytest.mark.parametrize(
    ("url", "article"),
    [
        pytest.param(
            "https://student.ntust.edu.tw/p/406-1053-152183,r1436.php?Lang=zh-tw",
            True,
            id="article",
        ),
        pytest.param(
            "https://www.academic.ntust.edu.tw/p/406-1048-149096,r1416.php", True, id="no query"
        ),
        pytest.param(
            "https://student.ntust.edu.tw/p/403-1053-1436-1.php?Lang=zh-tw",
            True,
            id="list page, as in v3",
        ),
        pytest.param(
            "https://docs.google.com/spreadsheets/d/EXAMPLE/edit?usp=sharing", False, id="document"
        ),
        pytest.param(
            "https://student.ntust.edu.tw/var/file/53/1053/img/2607/775989963.docx",
            False,
            id="file",
        ),
        pytest.param("https://lc.ntust.edu.tw/p/406-1070-1.pdf", False, id="pdf"),
        pytest.param("http://student.ntust.edu.tw/p/406-1053-1.php", False, id="http"),
        pytest.param("https://ntust.edu.tw/p/406-1053-1.php", False, id="no subdomain"),
    ],
)
def test_article_links(url: str, *, article: bool) -> None:
    """Requirement: Article pages give their content as minified HTML."""
    assert is_article(url) is article


def test_long_whitespace() -> None:
    """Requirement: Article pages give their content as minified HTML."""
    html = "<p>a" + " " * 30000 + "b</p>\n" + "<p>c" + "\t" * 30000 + "\n</p>"
    start = time.perf_counter()

    minified = minify(html)

    # v3's trailing-whitespace step backtracked through each run: seconds for 30,000 spaces.
    assert time.perf_counter() - start < 1
    assert minified == "<p>a b</p><p>c\n</p>"


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("https://example.com/x.ntust.edu.tw/p/1.php", id="path"),
        pytest.param(
            "https://www.google.com/url?q=https://student.ntust.edu.tw/p/406-1053-1.php",
            id="query",
        ),
        pytest.param("https://example.com?.ntust.edu.tw/p/1.php", id="query without a path"),
        pytest.param("https://example.com#.ntust.edu.tw/p/1.php", id="fragment"),
    ],
)
def test_other_hosts(url: str) -> None:
    """Requirement: Article pages give their content as minified HTML."""
    # v3's .* took any host before .ntust.edu.tw: such pages were fetched and sent to Gemini.
    assert not is_article(url)
