"""The Feedback config: v3's replies and the two new failure replies.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/config/ConfigSerializer.kt:6-18
    XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/resources/config.yaml:1-5
"""

import logging
from typing import TYPE_CHECKING, cast

import pytest
import yaml

from plugin_fakes import golden, load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.feedback.cog import Feedback
    from xincord.plugins.feedback.config import Config

GOLDEN = golden("feedback")
REPLIES = ("form_no_permission", "form_not_you", "form_success")  # v3's, all required
DEFAULTS = {
    "form_failure": "Failed to create the form",
    "form_submit_failure": "Failed to submit the feedback",
}


def loaded_config(bot: Bot) -> Config:
    """The config of the loaded plugin's cog.

    When a plugin's setup fails, as with the invalid files below, discord.py drops its modules, and
    the next load imports them again: an isinstance check against the class imported here would
    depend on the test order.
    """
    cog = bot.get_cog("Feedback")
    assert cog is not None
    return cast("Feedback", cog).config


def replies(config: Config) -> dict[str, str]:
    """The five replies of ``config``."""
    return {
        "form_no_permission": config.form_no_permission,
        "form_not_you": config.form_not_you,
        "form_success": config.form_success,
        "form_failure": config.form_failure,
        "form_submit_failure": config.form_submit_failure,
    }


def operator_file(**changes: str | None) -> str:
    """An operator's config.yaml: v3's three replies in English, with ``changes`` (None drops)."""
    values: dict[str, str | None] = {name: name.replace("_", " ") for name in REPLIES}
    values |= changes
    return yaml.safe_dump({key: value for key, value in values.items() if value is not None})


async def test_bundled_file(tmp_path: Path, store: Store) -> None:
    """Requirement: The config holds the replies."""
    bot = await load_plugin("Feedback", tmp_path / "plugins", store)

    assert replies(loaded_config(bot)) == GOLDEN["config"]


async def test_v3_file(tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The config holds the replies."""
    v3_file: str = GOLDEN["v3_config"]

    with caplog.at_level(logging.WARNING):
        bot = await load_plugin("Feedback", tmp_path / "plugins", store, config=v3_file)

    assert "unknown key enabled" in caplog.text
    v3_replies = {name: GOLDEN["config"][name] for name in REPLIES}
    assert replies(loaded_config(bot)) == v3_replies | DEFAULTS


@pytest.mark.parametrize(
    "text", ["x", "y" * 2000, " %user_name% "], ids=["short", "longest", "placeholder"]
)
async def test_reply_as_written(text: str, tmp_path: Path, store: Store) -> None:
    """Requirement: The config holds the replies."""
    config = operator_file(form_success=text, form_failure=text)

    bot = await load_plugin("Feedback", tmp_path / "plugins", store, config=config)

    assert loaded_config(bot).form_success == text
    assert loaded_config(bot).form_failure == text


@pytest.mark.parametrize("name", REPLIES)
async def test_missing_reply(
    name: str, tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config holds the replies."""
    config = operator_file(**{name: None})

    bot = await load_plugin("Feedback", tmp_path / "plugins", store, config=config)

    assert bot.loaded == ()
    assert f"{name}: Field required" in caplog.text


@pytest.mark.parametrize(
    "case",
    [
        ("", "String should match pattern"),
        (" \n", "String should match pattern"),
        ("z" * 2001, "String should have at most 2000 characters"),
    ],
    ids=["empty", "blank", "too-long"],
)
@pytest.mark.parametrize("name", [*REPLIES, *DEFAULTS])
async def test_invalid_reply(
    name: str,
    case: tuple[str, str],
    tmp_path: Path,
    store: Store,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Requirement: The config holds the replies."""
    text, error = case
    config = operator_file(**{name: text})

    bot = await load_plugin("Feedback", tmp_path / "plugins", store, config=config)

    assert bot.loaded == ()
    assert f"{name}: {error}" in caplog.text
