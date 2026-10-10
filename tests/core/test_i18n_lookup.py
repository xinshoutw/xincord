"""Lang lookups and command translation."""

from pathlib import Path
from typing import Any, Literal

import discord
import pytest
from discord import app_commands

from xincord.core.i18n import Lang, Translator, localized

LANG = Lang(
    plugin="Calc",
    default_locale="en-US",
    registers={"en-US": {"calc.name": "calc"}, "zh-TW": {"calc.name": "suan"}},
    texts={"en-US": {"p.a": "A", "p.b": "B"}, "zh-TW": {"p.a": "a-zh"}},
    templates={"en-US": {"message/result": Path("en-US/message/result.yml")}, "zh-TW": {}},
)
type Other = Literal[app_commands.TranslationContextLocation.other]
CONTEXT = app_commands.TranslationContext[Other, Any](
    location=app_commands.TranslationContextLocation.other,
    data=None,
)


async def translate(string: app_commands.locale_str, locale: discord.Locale) -> str | None:
    return await Translator().translate(string, locale, CONTEXT)


def test_per_key_fallback() -> None:
    """Requirement: Texts and templates fall back to the default locale."""

    assert LANG.text("p.a", "zh-TW") == "a-zh"
    assert LANG.text("p.b", "zh-TW") == "B"
    assert LANG.text("p.a", "ja") == "A"


def test_template_fallback() -> None:
    """Requirement: Texts and templates fall back to the default locale."""

    assert LANG.template("message/result", "zh-TW") == Path("en-US/message/result.yml")


def test_unknown_key_raises() -> None:
    """Requirement: Texts and templates fall back to the default locale."""

    with pytest.raises(LookupError, match=r"Calc.*p\.zzz"):
        LANG.text("p.zzz", "zh-TW")
    with pytest.raises(LookupError, match=r"Calc.*message/none"):
        LANG.template("message/none", "zh-TW")


async def test_translated_name() -> None:
    """Requirement: Commands are localized from register.yaml without fallback."""

    string = LANG.command("calc", "calc.name")

    assert string.message == "calc"
    assert await translate(string, discord.Locale.taiwan_chinese) == "suan"


async def test_no_fallback_for_commands() -> None:
    """Requirement: Commands are localized from register.yaml without fallback."""

    string = LANG.command("calc", "calc.name")

    assert await translate(string, discord.Locale.japanese) is None
    assert await translate(LANG.command("x", "x.name"), discord.Locale.taiwan_chinese) is None


async def test_plain_strings_are_not_translated() -> None:
    """Requirement: Commands are localized from register.yaml without fallback."""

    plain = app_commands.locale_str("calc")

    assert await translate(plain, discord.Locale.taiwan_chinese) is None


async def test_translated_from_the_table() -> None:
    """Requirement: Commands can be localized from a table."""

    string = localized("rules", {"zh-TW": "gui-ze", "ja": "kisoku"})

    assert string.message == "rules"
    assert await translate(string, discord.Locale.taiwan_chinese) == "gui-ze"
    assert await translate(string, discord.Locale.japanese) == "kisoku"


async def test_locale_missing_from_the_table() -> None:
    """Requirement: Commands can be localized from a table."""

    string = localized("rules", {"zh-TW": "gui-ze"})

    assert await translate(string, discord.Locale.japanese) is None
    assert await translate(localized("rules", {}), discord.Locale.taiwan_chinese) is None
