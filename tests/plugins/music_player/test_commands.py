"""v3's eleven guild commands: names, descriptions, options and localizations."""

from typing import TYPE_CHECKING, Any

from plugin_fakes import golden

if TYPE_CHECKING:
    from xincord.core.bot import Bot
    from xincord.core.command_tree import CommandTree

GOLDEN = golden("music_player")
LIMITS = ("max_length", "min_value", "max_value")


def localized(expected: dict[str, Any], index: int) -> dict[str, str]:
    """The en-US and zh-TW names (0) or descriptions (1) of a golden command or option."""
    return {locale: expected[locale][index] for locale in ("en-US", "zh-TW")}


async def test_command_payloads(bot: Bot) -> None:
    """Requirement: Commands keep v3's names, options and localizations."""
    tree: CommandTree = bot.tree  # pyright: ignore[reportAssignmentType]
    global_payload, payload = await tree.payloads(10)

    names = {expected["name"] for expected in GOLDEN["commands"]}
    assert not names & {command["name"] for command in global_payload}  # guild commands, as v3's
    assert [command["name"] for command in payload] == [
        expected["name"] for expected in GOLDEN["commands"]
    ]
    for command, expected in zip(payload, GOLDEN["commands"], strict=True):
        assert command["description"] == expected["description"]
        assert command["name_localizations"] == localized(expected, 0)
        assert command["description_localizations"] == localized(expected, 1)
        assert command.get("default_member_permissions") is None  # every member
        options = command.get("options", [])
        assert len(options) == len(expected.get("options", []))
        for option, wanted in zip(options, expected.get("options", []), strict=True):
            assert (option["name"], option["description"]) == (
                wanted["name"],
                wanted["description"],
            )
            assert (option["type"], option["required"]) == (wanted["type"], wanted["required"])
            assert option.get("autocomplete", False) == wanted["autocomplete"]
            assert {key: option.get(key) for key in LIMITS} == {
                key: wanted.get(key) for key in LIMITS
            }
            assert option["name_localizations"] == localized(wanted, 0)
            assert option["description_localizations"] == localized(wanted, 1)
