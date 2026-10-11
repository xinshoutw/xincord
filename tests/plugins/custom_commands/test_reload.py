"""Reloading the plugin after the operator edited its config."""

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

from plugin_fakes import watch_syncs
from xincord.core.bot import Bot

if TYPE_CHECKING:
    import pytest

    from conftest import Operator
    from xincord.core.command_tree import CommandTree

NAMES = ["cub-none-card", "tsib-none-card", "ctcb-none-card", "ctcb-remit", "chpytwtp-remit"]
# cub-none-card renamed, rules added, the other four removed.
EDITED = """\
commands:
  - name: cub-card
    description: generate message
    template: cub-none-card
  - name: rules
    description: Post the rules
"""


async def names(bot: Bot) -> list[str]:
    """The names of the guild commands that the bot would upload."""
    _, guild_payload = await cast("CommandTree", bot.tree).payloads()
    return [entry["name"] for entry in guild_payload]


async def test_edited_config(operator: Operator, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement: Config changes apply on reload."""
    bot = await operator.load()
    operator.template("rules", 'content: "Be nice"\n')
    (operator.directory / "config.yaml").write_text(EDITED, encoding="utf-8")
    syncs = watch_syncs(bot, operator.store, monkeypatch)

    def is_ready(_: Bot) -> bool:
        return True

    monkeypatch.setattr(Bot, "is_ready", is_ready)
    monkeypatch.setattr(Bot, "guilds", property(lambda _: [SimpleNamespace(id=1, name="One")]))

    summary = await bot.reload("CustomCommands")

    assert summary == "Reloaded: CustomCommands."
    assert await names(bot) == ["cub-card", "rules"]
    assert syncs == [("global", False), (1, False)]  # the guild's payload changed


async def test_broken_edit(operator: Operator) -> None:
    """Requirement: Config changes apply on reload."""
    bot = await operator.load()
    (operator.directory / "config.yaml").write_text("commands:\n  - name: rules\n", "utf-8")

    summary = await bot.reload("CustomCommands")

    assert summary.startswith("Reload failed: plugin CustomCommands failed to reload: ")
    assert "commands.0.description: Field required" in summary
    assert await names(bot) == NAMES
    assert bot.get_cog("CustomCommands") is not None
