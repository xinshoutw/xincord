"""The HTML tree that stands for Ksoup: v3's selectors, its text() and its outer HTML.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementParser.kt:108-236
"""

import pytest

from xincord.plugins.ntust_announcements.markup import parse

NBSP = chr(0xA0)
IDEOGRAPHIC_SPACE = chr(0x3000)
ZERO_WIDTH_SPACE = chr(0x200B)
SOFT_HYPHEN = chr(0xAD)


def texts(html: str, selector: str) -> list[str]:
    """The text of each element of ``html`` that ``selector`` matches."""
    return [element.text() for element in parse(html).select(selector)]


def test_compound_selectors() -> None:
    """Requirement: Board pages list their announcements."""
    html = (
        '<div class="row listBS">a</div><div class="row">b</div>'
        '<div class="ROW listbs extra">c</div><p class="row listBS">d</p>'
        '<div id="Dyn_2_3" class="M23">e</div><div id="Dyn_2_2" class="M23">f</div>'
    )

    # Classes compare without case, as jsoup's hasClass; the tag and the ID must match.
    assert texts(html, "div.row.listBS") == ["a", "c"]
    assert texts(html, ".row") == ["a", "b", "c", "d"]
    assert texts(html, "div#Dyn_2_3.M23") == ["e"]
    assert texts(html, "div.M23") == ["e", "f"]
    assert texts(html, "#dyn_2_3") == []  # IDs compare with case


def test_descendant_selectors() -> None:
    """Requirement: Board pages list their announcements."""
    html = (
        '<div class="row listBS"><div class="d-item d-title col-sm-12"><div class="mbox">'
        '<div class="d-txt"><div class="mtitle"><a href="/one">One</a><a href="/two">Two</a>'
        "</div></div></div></div></div>"
        '<div class="mtitle"><a href="/three">Three</a></div>'
    )
    document = parse(html)
    row = document.select_first("div.row.listBS")
    assert row is not None

    chain = "div.d-item.d-title.col-sm-12 div.mbox div.d-txt div.mtitle a"
    assert [link.attr("href") for link in row.select(chain)] == ["/one", "/two"]
    assert [link.attr("href") for link in document.select("div.mtitle a")] == [
        "/one",
        "/two",
        "/three",
    ]
    # The element itself counts, as an ancestor and as a match, as in jsoup's select.
    assert [element.tag for element in row.select("div.listBS")] == ["div"]
    assert len(row.select("div.row div.mtitle a")) == 2
    assert document.select_first("table") is None


def test_omitted_end_tags() -> None:
    """Requirement: Board pages list their announcements."""
    # HTML lets pages omit these end tags; an HTML5 parser such as jsoup adds the tbody.
    html = (
        '<table class="listTB table"><tr><td><a href="/a">A</a><td>2026-10-01'
        "<tr><td><a href=/b>B</a><td>2026-10-02</table>"
        "<ul><li>one<li>two</ul><dl><dt>term<dd>meaning</dl><p>first<div>block</div>"
    )
    document = parse(html)
    table = document.select_first("table.listTB.table")
    assert table is not None

    rows = table.select("tbody tr")
    assert [[cell.text() for cell in row.select("td")] for row in rows] == [
        ["A", "2026-10-01"],
        ["B", "2026-10-02"],
    ]
    assert texts(html, "li") == ["one", "two"]
    assert texts(html, "dt") == ["term"]
    assert texts(html, "p") == ["first"]  # a block closes the paragraph


def test_cells_without_rows() -> None:
    """Requirement: Board pages list their announcements."""
    # A cell straight in a table gets the row and the body that jsoup would add.
    document = parse("<table><td>alone</td></table>")

    assert [cell.text() for cell in document.select("table tbody tr td")] == ["alone"]


def test_end_tags() -> None:
    """Requirement: Board pages list their announcements."""
    # An end tag closes the nearest open element of its name; a stray one changes nothing; void
    # elements and raw text hold no elements.
    html = (
        "<div class=outer><span><b>bold</span>after</div></p><div class=next>next</div>"
        "<br><img src=x.png><script>var a = '<div class=fake>';</script>"
    )

    document = parse(html)

    assert texts(html, "div.outer") == ["boldafter"]
    assert texts(html, "div.next") == ["next"]
    assert document.select("div.fake") == []
    assert [
        len(element.children) for element in document.select("br") + document.select("img")
    ] == [
        0,
        0,
    ]


def test_attributes() -> None:
    """Requirement: Board pages list their announcements."""
    link = parse('<a href="/p/1.php?a=1&amp;b=2" href="/second" data-x>x</a>').select_first("a")
    assert link is not None

    assert link.attr("href") == "/p/1.php?a=1&b=2"  # entities decoded; the first one wins
    assert link.attr("data-x") == ""
    assert link.attr("title") == ""


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        pytest.param("<a>\n\t\t  One \n two\t</a>", "One two", id="collapsed"),
        pytest.param(f"<a>{NBSP}One{NBSP}{NBSP}two{NBSP}</a>", "One two", id="no-break spaces"),
        pytest.param(f"<a>One{ZERO_WIDTH_SPACE}{SOFT_HYPHEN}two</a>", "Onetwo", id="invisible"),
        pytest.param("<a>One<br>two</a>", "One two", id="line break"),
        pytest.param("<a><div>One</div>two</a>", "One two", id="block"),
        pytest.param("<a>One<b>two</b> three</a>", "Onetwo three", id="inline"),
        pytest.param("<a>A &amp; B &quot;C&quot;</a>", 'A & B "C"', id="entities"),
        pytest.param(
            f"<a>{IDEOGRAPHIC_SPACE}One{IDEOGRAPHIC_SPACE}</a>",
            f"{IDEOGRAPHIC_SPACE}One{IDEOGRAPHIC_SPACE}",
            id="ideographic spaces stay for Kotlin's trim",
        ),
    ],
)
def test_text(html: str, expected: str) -> None:
    """Requirement: Board pages list their announcements."""
    assert texts(html, "a") == [expected]


def test_outer_html() -> None:
    """Requirement: Article pages give their content as minified HTML."""
    html = (
        '<body><div id="Dyn_2_3" class="M23  " data-x>\n'
        "<!-- a comment --><p title='say \"hi\" &amp; go'>A &lt;tag&gt; &amp; text<br/>"
        "<img src=a.png></p>\n<style>p > a { color: red; }</style></div></body>"
    )
    container = parse(html).select_first("div.M23")
    assert container is not None

    assert container.outer_html() == (
        '<div id="Dyn_2_3" class="M23  " data-x>\n'
        '<p title="say &quot;hi&quot; &amp; go">A &lt;tag&gt; &amp; text<br>'
        '<img src="a.png"></p>\n<style>p > a { color: red; }</style></div>'
    )


def test_end_tags_stay_in_their_cell() -> None:
    """Requirement: Board pages list their announcements."""
    # An end tag inside a table cell closes nothing outside it, as in HTML.
    html = "<div class=outer><table><tr><td><span>x</div>y</td></tr></table>z</div>"
    document = parse(html)

    assert texts(html, "td") == ["xy"]
    assert texts(html, "div.outer") == ["xy z"]  # the table is a block, as in jsoup
    assert len(document.select("div.outer table td span")) == 1


def test_raw_text_is_no_text() -> None:
    """Requirement: Board pages list their announcements."""
    # jsoup keeps scripts and styles as data, which text() leaves out.
    assert texts("<a>One<script>var x = 1;</script><style>p {}</style>two</a>", "a") == ["Onetwo"]
    assert texts("<script>var x = 1;</script>", "script") == [""]


@pytest.mark.parametrize("selector", ["a > b", "a, b", "*", "", "a[href]"])
def test_unsupported_selectors(selector: str) -> None:
    """Requirement: Board pages list their announcements."""
    with pytest.raises(ValueError, match="unsupported selector"):
        parse("<a>x</a>").select(selector)


def test_deep_nesting() -> None:
    """Requirement: Board pages list their announcements."""
    # Unclosed elements nest; a page 3000 levels deep must not exhaust Python's recursion limit.
    container = parse('<div class="M23">' + "<span>" * 3000 + "deep</div>").select_first("div")
    assert container is not None

    assert container.text() == "deep"
    assert container.outer_html().startswith('<div class="M23"><span><span>')
    assert container.outer_html().endswith("deep" + "</span>" * 3000 + "</div>")


@pytest.mark.xfail(strict=True, reason="Board pages list their announcements")
def test_self_closing_tags() -> None:
    """Requirement: Board pages list their announcements."""
    # HTML ignores the slash of a non-void start tag, as jsoup does: the link keeps its title.
    html = '<table class="listTB table"><tbody><tr><td><a href="/p/1.php" />Title</td>'
    html += "<td>2026-10-11</td></tr></tbody></table><br/><p>after</p>"

    assert texts(html, "td a") == ["Title"]
    assert texts(html, "p") == ["after"]


@pytest.mark.xfail(strict=True, reason="Board pages list their announcements")
def test_class_separators() -> None:
    """Requirement: Board pages list their announcements."""
    # jsoup splits classes at Java's whitespace, which leaves out no-break spaces.
    assert texts(f'<div class="row{NBSP}listBS">a</div>', "div.row.listBS") == []
    assert texts('<div class="row\tlistBS">b</div>', "div.row.listBS") == ["b"]
    assert texts(f'<div class="row{IDEOGRAPHIC_SPACE}listBS">c</div>', "div.row.listBS") == ["c"]
