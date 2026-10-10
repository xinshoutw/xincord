"""The star text of a review and the star count of an ID.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/Feedbacker.kt:139-145
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/resources/lang/en-US/message/ask-message.yaml:13-54
"""

import pytest

from plugin_fakes import golden
from xincord.plugins.feedbacker.form import star_count, stars

GOLDEN = golden("feedbacker")


@pytest.mark.parametrize("count", range(6))
def test_star_counts(count: int) -> None:
    """Requirement: Stars follow v3's text."""
    assert stars(count) == GOLDEN["fb_stars"][count]


@pytest.mark.parametrize("count", range(6))
def test_star_count_of_an_id(count: int) -> None:
    """Requirement: Stars follow v3's text."""
    assert star_count(str(count)) == count


@pytest.mark.parametrize("text", ["6", "-1", "x", "", "03", " 3", "3.0", "+3"])
def test_invalid_star_count(text: str) -> None:
    """Requirement: Stars follow v3's text."""
    with pytest.raises(ValueError, match="star count"):
        star_count(text)
