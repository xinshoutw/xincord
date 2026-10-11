"""One language per message: the plugin's files for the locale, else v3's zh or English choice.

v3 chose its hard-coded texts by a ``zh`` prefix and its templates by the locale's directory, else
the configured default, so en-GB users saw English texts with zh-TW buttons.
"""

from typing import TYPE_CHECKING, cast

import pytest

from plugin_fakes import golden, load_plugin
from xincord.plugins.giveaway.texts import Texts, language

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.plugins.giveaway.cog import Giveaway

GOLDEN = golden("giveaway")


def plugin_lang(bot: Bot) -> Lang:
    """The loaded plugin's lang files."""
    cog = bot.get_cog("Giveaway")
    assert cog is not None
    return cast("Giveaway", cog).lang


@pytest.mark.parametrize(
    ("locale", "chosen"),
    [
        ("en-US", "en-US"),
        ("zh-TW", "zh-TW"),
        ("zh-CN", "zh-TW"),
        ("en-GB", "en-US"),
        ("ja", "en-US"),
        ("unknown", "en-US"),
    ],
)
async def test_language(bot: Bot, locale: str, chosen: str) -> None:
    """Requirement: Each message uses one language."""
    lang = plugin_lang(bot)

    assert language(lang, locale) == chosen
    # The templates come from the same locale as the texts.
    assert lang.template("message/create-giveaway", chosen).parent.parent.name == chosen


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_texts(bot: Bot, locale: str) -> None:
    """Requirement: Each message uses one language."""
    texts = Texts(plugin_lang(bot), locale)
    expected = GOLDEN["texts"][locale]

    assert texts.get("post.join") == expected["join"]
    # Values are inserted as written, in one pass.
    assert texts.get("post.title", {"ga@title": "%ga@id%"}) == expected["title-placeholder"]


async def test_operator_locale(tmp_path: Path, store: Store) -> None:
    """Requirement: Each message uses one language."""
    root = tmp_path / "plugins"
    lang_dir = root / "Giveaway" / "lang" / "ja"
    lang_dir.mkdir(parents=True)
    (lang_dir / "text.yaml").write_text('post:\n  join: "join-ja"\n', encoding="utf-8")

    bot = await load_plugin("Giveaway", root, store)
    lang = plugin_lang(bot)

    assert language(lang, "ja") == "ja"
    assert Texts(lang, "ja").get("post.join") == "join-ja"
    # A text that the operator's locale lacks comes from defaultLocale, zh-TW.
    assert Texts(lang, "ja").get("post.draw") == GOLDEN["texts"]["zh-TW"]["draw"]


async def test_missing_text(tmp_path: Path, store: Store) -> None:
    """Requirement: Each message uses one language."""
    root = tmp_path / "plugins"
    english = root / "Giveaway" / "lang" / "en-US"
    english.mkdir(parents=True)
    # An operator's file without most texts; the export never overwrites it.
    (english / "text.yaml").write_text('post:\n  join: "Join"\n', encoding="utf-8")

    bot = await load_plugin("Giveaway", root, store)
    texts = Texts(plugin_lang(bot), "en-US")

    assert texts.get("post.join") == "Join"
    # A text that the locale lacks comes from defaultLocale, zh-TW.
    assert texts.get("post.draw") == GOLDEN["texts"]["zh-TW"]["draw"]
