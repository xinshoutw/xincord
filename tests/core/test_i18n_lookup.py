"""Lang lookups and command translation."""

from pathlib import Path
from typing import Any, Literal

import discord
import pytest
from discord import app_commands

from xincord.core.i18n import Lang, Translator


def xfail(requirement: str) -> pytest.MarkDecorator:
    return pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=requirement)


FALLBACK = xfail("Texts and templates fall back to the default locale")
COMMANDS = xfail("Commands are localized from register.yaml without fallback")

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


@FALLBACK
def test_per_key_fallback() -> None:
    assert LANG.text("p.a", "zh-TW") == "a-zh"
    assert LANG.text("p.b", "zh-TW") == "B"
    assert LANG.text("p.a", "ja") == "A"


@FALLBACK
def test_template_fallback() -> None:
    assert LANG.template("message/result", "zh-TW") == Path("en-US/message/result.yml")


@FALLBACK
def test_unknown_key_raises() -> None:
    with pytest.raises(LookupError, match=r"Calc.*p\.zzz"):
        LANG.text("p.zzz", "zh-TW")
    with pytest.raises(LookupError, match=r"Calc.*message/none"):
        LANG.template("message/none", "zh-TW")


@COMMANDS
async def test_translated_name() -> None:
    string = LANG.command("calc", "calc.name")

    assert string.message == "calc"
    assert await translate(string, discord.Locale.taiwan_chinese) == "suan"


@COMMANDS
async def test_no_fallback_for_commands() -> None:
    string = LANG.command("calc", "calc.name")

    assert await translate(string, discord.Locale.japanese) is None
    assert await translate(LANG.command("x", "x.name"), discord.Locale.taiwan_chinese) is None


@COMMANDS
async def test_plain_strings_are_not_translated() -> None:
    plain = app_commands.locale_str("calc")

    assert await translate(plain, discord.Locale.taiwan_chinese) is None
