"""The alerts' texts, their mentions and how often a channel hears about a course."""

import re
from typing import TYPE_CHECKING

import pytest

from plugin_fakes import golden
from xincord.plugins.ntust_course_watch.alerts import (
    Alerts,
    Post,
    available_posts,
    escape,
    full_post,
)
from xincord.plugins.ntust_course_watch.courses import Course

if TYPE_CHECKING:
    from xincord.plugins.ntust_course_watch.cog import NtustCourseWatch

GOLDEN = golden("ntust_course_watch")
NAME = GOLDEN["courses"]["CE162A001"]["name"]
COURSE = Course("CE162A001", NAME, 25, 60)
MENTION = re.compile(r"<@(\d+)>")


def units(text: str) -> int:
    """Discord's length of ``text``, in UTF-16 code units."""
    return len(text.encode("utf-16-le")) // 2


def test_available_text(cog: NtustCourseWatch) -> None:
    """Requirement: Channels hear about courses with seats."""
    # v3's text: the second, the spoilered mentions, the masked course-selection link, the code.
    assert available_posts(cog.lang, COURSE, (1, 2), 7) == [
        Post(GOLDEN["alerts"]["available"], (1, 2))
    ]


def test_many_members(cog: NtustCourseWatch) -> None:
    """Requirement: Channels hear about courses with seats."""
    members = tuple(1_000_000_000_000_000_000 + number for number in range(120))

    posts = available_posts(cog.lang, COURSE, members, 59)

    # v3's one message exceeded 2000 characters, which JDA refused by throwing in its loop.
    assert len(posts) > 1
    for post in posts:
        assert units(post.content) <= 2000
        assert len(post.users) <= 100
        assert tuple(int(user) for user in MENTION.findall(post.content)) == post.users
        assert post.content.startswith("59 ||")
        assert post.content.endswith("```\nCE162A001\n```")
    assert tuple(user for post in posts for user in post.users) == members


def test_hundred_users_a_post(cog: NtustCourseWatch) -> None:
    """Requirement: Channels hear about courses with seats."""
    members = tuple(range(1, 151))  # short IDs: the length allows them all in one message

    posts = available_posts(cog.lang, COURSE, members, 0)

    # Discord takes at most 100 users in a message's allowed mentions.
    assert [len(post.users) for post in posts] == [100, 50]
    assert tuple(user for post in posts for user in post.users) == members


@pytest.mark.parametrize(
    ("name", "escaped"),
    [
        pytest.param("[EMI] Calculus", "\\[EMI\\] Calculus", id="brackets"),
        pytest.param("Calculus\\", "Calculus\\\\", id="backslash"),
        pytest.param("Calculus (I)", "Calculus (I)", id="parentheses stay"),
    ],
)
def test_escaped_names(cog: NtustCourseWatch, name: str, escaped: str) -> None:
    """Requirement: Channels hear about courses with seats."""
    assert escape(name) == escaped
    [post] = available_posts(cog.lang, Course("CE162A001", name, 0, 1), (1,), 0)
    assert f"[Course Available: {escaped}](https://" in post.content


def test_throttle() -> None:
    """Requirement: Channels hear about courses with seats."""
    alerts = Alerts(60)

    assert alerts.seats("CE162A001", (5, 6), 1000.0) == [5, 6]
    assert alerts.seats("CE162A001", (5, 6, 7), 1059.9) == [7]  # 7 never heard about it
    assert alerts.seats("CE162A002", (5,), 1059.9) == [5]  # another course
    assert alerts.seats("CE162A001", (5, 6), 1060.0) == [5, 6]


def test_full_text(cog: NtustCourseWatch) -> None:
    """Requirement: Channels hear once when a course fills."""
    # v3 passed the members to mentionUsers, but the text mentions nobody: it pinged nobody.
    assert full_post(cog.lang, COURSE) == Post(GOLDEN["alerts"]["full"], ())


def test_owed_full_alerts() -> None:
    """Requirement: Channels hear once when a course fills."""
    alerts = Alerts(60)
    assert alerts.filled("CE162A001", (5,)) == []  # no available alert yet

    alerts.seats("CE162A001", (5, 6), 0.0)

    assert alerts.filled("CE162A001", (5, 7)) == [5]  # 7 got no available alert
    assert alerts.filled("CE162A001", (5, 6)) == [6]  # 5 got its full alert


def test_seats_come_and_go() -> None:
    """Requirement: Channels hear once when a course fills."""
    alerts = Alerts(60)
    told: list[str] = []

    for second in range(0, 120, 3):  # seats at every other check, three seconds apart
        if second % 6 == 0:
            told += ["available"] * len(alerts.seats("CE162A001", (5,), float(second)))
        else:
            told += ["full"] * len(alerts.filled("CE162A001", (5,)))

    # v3 posted at each of them; each available alert is followed by one full alert at most.
    assert told == ["available", "full", "available", "full"]


def test_forget_unregistered() -> None:
    """Requirement: Channels hear about courses with seats."""
    alerts = Alerts(60)
    alerts.seats("CE162A001", (5, 6), 0.0)
    alerts.seats("CE162A002", (5,), 0.0)

    alerts.keep({"CE162A001": {6: (1,)}})

    # A channel that registers again hears about the course at once.
    assert alerts.seats("CE162A001", (5, 6), 1.0) == [5]
    assert alerts.seats("CE162A002", (5,), 1.0) == [5]
    assert alerts.filled("CE162A001", (6,)) == [6]
