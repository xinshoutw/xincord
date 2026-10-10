"""Validating the config at load: every problem disables the plugin with the key named.

v3 fixed its commands in code, where Discord's rules held by construction:
    XsDiscordBotKt@3a59607:Plugins/SimpleCommand/src/main/kotlin/simplecommand/command/Register.kt:39-60
"""

import logging
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from conftest import Operator

TOO_LONG = "x" * 101
# One entry, and the key that the error about it names.
ENTRIES = [
    ("{name: Pay Now, description: Pay}", "commands.0.name"),
    (
        "{name: pay, description: Pay, localizations: {zh-TW: {name: pay now}}}",
        "commands.0.localizations.zh-TW.name",
    ),
    ('{name: pay, description: ""}', "commands.0.description"),
    (f"{{name: pay, description: {TOO_LONG}}}", "commands.0.description"),
    (
        f"{{name: pay, description: Pay, localizations: {{ja: {{description: {TOO_LONG}}}}}}}",
        "commands.0.localizations.ja.description",
    ),
    (
        "{name: pay, description: Pay, localizations: {zh: {name: fu}}}",
        "commands.0.localizations.zh",
    ),
    ("{name: pay, description: Pay, permissions: [admin]}", "commands.0.permissions.0"),
    ("{name: pay, description: Pay, guilds: [0]}", "commands.0.guilds.0"),
]
# Two entries that share a name in a locale, and the key of the second one.
DUPLICATES = [
    ("{name: pay, description: Pay}", "{name: pay, description: Pay again}", "commands.1.name"),
    (
        "{name: pay, description: Pay, localizations: {zh-TW: {name: fu}}}",
        "{name: fee, description: Fee, localizations: {zh-TW: {name: fu}}}",
        "commands.1.localizations.zh-TW.name",
    ),
    (
        "{name: pay, description: Pay}",
        "{name: fee, description: Fee, localizations: {zh-TW: {name: pay}}}",
        "commands.1.localizations.zh-TW.name",
    ),
    (
        "{name: fee, description: Fee, localizations: {zh-TW: {name: pay}}}",
        "{name: pay, description: Pay}",
        "commands.1.name",
    ),
]
SIX_ROWS = "content: links\ncomponents:\n" + (
    "  - !ButtonsComponent\n    buttons: [{style: 5, url: 'https://e.x', label: L}]\n" * 6
)
# Templates that the plugin cannot post, and why, as the renderer says.
UNPOSTABLE = [
    (
        "components:\n  - !ButtonsComponent\n    buttons: [{uid: {action: pay}, label: Pay}]\n",
        "components with a uid need an ID builder",
    ),
    ("model_key: message\n", "no model named 'message' was supplied"),
    (
        (
            "is_components_v2: true\n"
            "components_v2:\n"
            "  - {type: action_row, components: [{type: button, label: Pay, uid: {action: pay}}]}\n"
        ),
        "components with a uid need an ID builder",
    ),
    (
        (
            "is_components_v2: true\n"
            "components_v2:\n  - {type: file_display, file_path: missing.pdf}\n"
        ),
        "cannot attach missing.pdf",
    ),
    (SIX_ROWS, "row cannot be negative or greater than or equal to 5"),
]


async def refused(operator: Operator, config: str, caplog: pytest.LogCaptureFixture) -> str:
    """Load the plugin with ``config``; check that it did not load and return the log."""
    with caplog.at_level(logging.ERROR):
        bot = await operator.load(config)

    assert bot.loaded == ()
    return caplog.text


@pytest.mark.parametrize(
    ("entry", "key"),
    ENTRIES,
    ids=["name", "zh-TW-name", "empty", "long", "ja-long", "locale", "permission", "guild"],
)
async def test_invalid_values(
    operator: Operator, caplog: pytest.LogCaptureFixture, entry: str, key: str
) -> None:
    """Requirement: The config is validated at load."""
    operator.template("pay", 'content: "Pay here"\n')

    log = await refused(operator, f"commands:\n  - {entry}\n", caplog)

    assert f"config.yaml: {key}" in log


@pytest.mark.parametrize(
    ("first", "second", "key"),
    DUPLICATES,
    ids=["base", "zh-TW", "zh-TW-and-base", "base-and-zh-TW"],
)
async def test_duplicate_names(
    operator: Operator, caplog: pytest.LogCaptureFixture, first: str, second: str, key: str
) -> None:
    """Requirement: The config is validated at load."""
    operator.template("pay", 'content: "Pay here"\n')
    operator.template("fee", 'content: "Fees"\n')

    log = await refused(operator, f"commands:\n  - {first}\n  - {second}\n", caplog)

    assert f"config.yaml: {key}: " in log


async def test_too_many_commands(operator: Operator, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The config is validated at load."""
    entries = "".join(
        f"  - {{name: c{index}, description: d, template: cub-none-card}}\n" for index in range(100)
    )

    log = await refused(operator, f"commands:\n{entries}", caplog)

    # The core's /xincord takes one of the 100 places.
    assert "config.yaml: commands: 100 commands, more than the 99 places left" in log


async def test_missing_template(operator: Operator, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The config is validated at load."""
    operator.template("rules", 'content: "Be nice"\n', locale="en-US")

    log = await refused(operator, "commands:\n  - {name: rules, description: Rules}\n", caplog)

    assert "config.yaml: commands.0.template: " in log


@pytest.mark.parametrize(
    ("template", "reason"),
    UNPOSTABLE,
    ids=["uid", "model_key", "v2-uid", "missing-file", "six-rows"],
)
async def test_template_that_cannot_be_posted(
    operator: Operator, caplog: pytest.LogCaptureFixture, template: str, reason: str
) -> None:
    """Requirement: The config is validated at load."""
    operator.template("faq", 'content: "Ask in #help"\n')
    operator.template("faq", template, locale="en-US")

    log = await refused(operator, "commands:\n  - {name: faq, description: FAQ}\n", caplog)

    assert f"en-US/message/faq.yaml: cannot be posted: {reason}" in log


async def test_link_button_with_a_uid(operator: Operator) -> None:
    """Requirement: The config is validated at load."""
    operator.template(
        "site",
        "content: Our site\n"
        "components:\n"
        "  - !ButtonsComponent\n"
        "    buttons: [{style: 5, url: 'https://e.x', label: Site, uid: {action: open}}]\n",
    )

    bot = await operator.load("commands:\n  - {name: site, description: Site}\n")

    assert bot.loaded == ("CustomCommands",)


async def test_name_with_a_line_break(operator: Operator, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The config is validated at load."""
    operator.template("pay", 'content: "Pay here"\n')

    log = await refused(operator, 'commands:\n  - {name: "pay\\n", description: Pay}\n', caplog)

    assert "config.yaml: commands.0.name" in log


async def test_missing_commands(operator: Operator, caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: The config is validated at load."""
    log = await refused(operator, "enabled: true\n", caplog)

    assert "config.yaml: commands: Field required" in log
