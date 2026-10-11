"""Each board's posted links in the store, as v3's MongoDB document.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementCacheManager.kt:25-68
    XsDiscordBotKt@3a59607:Plugins/NtustManager/src/main/kotlin/ntustmanager/announcement/AnnouncementCacheManager.kt:181-224
"""

import json
from typing import TYPE_CHECKING

import pytest

from xincord.plugins.ntust_announcements.pages import Link
from xincord.plugins.ntust_announcements.store import (
    KEEP,
    NAMESPACE,
    DataError,
    Posted,
    parse_posted,
    posted_document,
    remember,
)

if TYPE_CHECKING:
    from xincord.core.storage import JSON, Store

BOARD = "STUDENT_DORMITORY"
# v3's itemTypeName, which Moshi wrote when the list was not empty (CacheCollectionManager.kt:143).
ITEM_TYPE = "tw.xinshou.discord.plugin.ntustmanager.announcement.AnnouncementLink"


def link(number: int, title: str = "") -> Link:
    """An article of the dormitory board."""
    url = f"https://student.ntust.edu.tw/p/406-1053-{number},r1436.php?Lang=zh-tw"
    return Link(BOARD, url, title or f"Notice {number}")


def urls(links: tuple[Link, ...]) -> list[str]:
    return [entry.url for entry in links]


def test_document_shape() -> None:
    """Requirement: Each board remembers what it posted."""
    document = posted_document([link(1), link(2)])

    # v3's TypedListWrapper value, Moshi's field order, without itemTypeName.
    assert json.dumps(document) == json.dumps(
        {
            "items": [
                {"type": BOARD, "url": link(1).url, "title": "Notice 1"},
                {"type": BOARD, "url": link(2).url, "title": "Notice 2"},
            ]
        }
    )
    assert posted_document([]) == {"items": []}


def test_v3_document() -> None:
    """Requirement: Each board remembers what it posted."""
    document: JSON = {
        "items": [
            {"type": BOARD, "url": link(1).url, "title": "Notice 1"},
            {"type": "OTHER_BOARD", "url": link(2).url, "title": "Notice 2"},
        ],
        "itemTypeName": ITEM_TYPE,
    }

    assert parse_posted(document) == (link(1), Link("OTHER_BOARD", link(2).url, "Notice 2"))
    assert parse_posted({"items": []}) == ()


@pytest.mark.parametrize(
    "document",
    [
        pytest.param([], id="a list"),
        pytest.param("items", id="a text"),
        pytest.param({}, id="no items"),
        pytest.param({"items": "x"}, id="items not a list"),
        pytest.param({"items": ["x"]}, id="an item not an object"),
        pytest.param({"items": [{"type": BOARD, "url": "u"}]}, id="no title"),
        pytest.param({"items": [{"type": BOARD, "url": 1, "title": "t"}]}, id="a number"),
    ],
)
def test_broken_documents(document: JSON) -> None:
    """Requirement: Each board remembers what it posted."""
    with pytest.raises(DataError):
        parse_posted(document)


def test_remember() -> None:
    """Requirement: Each board remembers what it posted."""
    stored = (link(3), link(2), link(1))
    page = (link(5), link(4, "Failed"), link(3, "Renamed"), link(2), link(2))

    kept = remember(stored, page, {*urls(stored), link(5).url})

    # The page's posted links in its order, once each, with the page's titles; then the stored
    # links that left the page. The link that failed is not kept, so the next pass posts it.
    assert kept == (link(5), link(3, "Renamed"), link(2), link(1))


def test_bounded() -> None:
    """Requirement: Each board remembers what it posted."""
    left = tuple(link(number) for number in range(1000, 850, -1))  # 150, the most recent first
    page = (link(2000), link(1999))

    kept = remember((*page, *left), page, urls((*page, *left)))

    assert kept == (*page, *left[:KEEP])


async def test_load_and_save(store: Store) -> None:
    """Requirement: Each board remembers what it posted."""
    posted = Posted(store)
    assert await posted.load(BOARD) == ()  # no document: nothing posted

    await posted.save(BOARD, [link(2), link(1)])

    assert await posted.load(BOARD) == (link(2), link(1))
    assert await store.get(NAMESPACE, BOARD) == posted_document([link(2), link(1)])


async def test_broken_document_stays(store: Store) -> None:
    """Requirement: Each board remembers what it posted."""
    await store.put(NAMESPACE, BOARD, {"items": "broken"})

    with pytest.raises(DataError):
        await Posted(store).load(BOARD)

    assert await store.get(NAMESPACE, BOARD) == {"items": "broken"}
