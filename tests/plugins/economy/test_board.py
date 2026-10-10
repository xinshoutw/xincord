"""``/top-money`` and ``/top-cost``, and the check of their templates at load.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/Economy.kt:42-53
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/MessageReplier.kt:44-68
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/storage/JsonImpl.kt:75-120
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/resources/lang/en-US/message/top-money.yaml:1-9
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/resources/lang/en-US/message/top-cost.yaml:1-9
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/resources/lang/zh-TW/message/top-money.yaml:1-9
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/resources/lang/zh-TW/message/top-cost.yaml:1-9
"""

import textwrap
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import discord
import pytest

from discord_fakes import FakeGuild, FakeInteraction, FakeMember, embed_dict
from plugin_fakes import golden, load_plugin
from xincord.plugins.economy.store import NAMESPACE, change
from xincord.plugins.economy.wallet import OPERATIONS, Wallet

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.storage import Store
    from xincord.plugins.economy.cog import Economy

GOLDEN = golden("economy")
EN = discord.Locale.american_english
ZH = discord.Locale.taiwan_chinese
GUILD = FakeGuild(id=10)
ADMIN = FakeMember(GUILD, id=1, name="admin")  # listed in CONFIG
CONFIG = "admin_id: [1]\nboard_user_show_limit: 3\n"  # the conftest's
# The golden boards' wallets in guild 10; user 4 is fourth on the money board, past the limit.
WALLETS = {
    2: Wallet(money=50, cost=5),
    1: Wallet(money=20, cost=0),
    3: Wallet(money=20, cost=9),
    4: Wallet(money=1, cost=1),
}


def run(name: str, *, locale: discord.Locale = EN) -> FakeInteraction:
    """The board ``name`` asked for by the administrator in guild 10."""
    return FakeInteraction(
        {"type": 1, "name": name},
        command=SimpleNamespace(name=name),
        user=ADMIN,
        guild=GUILD,
        locale=locale,
    )


def edited(interaction: FakeInteraction) -> tuple[str, list[dict[str, Any]]]:
    """The content and the embeds of the one edit of the deferred response."""
    [(method, fields)] = interaction.sent
    assert method == "edit_original_response"
    embeds = cast("tuple[discord.Embed, ...]", fields["embeds"])
    return cast("str", fields["content"]), [embed_dict(embed) for embed in embeds]


async def give(store: Store) -> None:
    """The wallets of ``WALLETS``."""
    for user_id, wallet in WALLETS.items():
        await change(store, 10, user_id, OPERATIONS["set-money"], wallet.money)
        await change(store, 10, user_id, OPERATIONS["set-cost"], wallet.cost)


def operator_template(root: Path, locale: str, name: str, text: str) -> Path:
    """Write an operator's message template under ``root``, before the plugin exports its own."""
    path = root / "Economy" / "lang" / locale / "message" / f"{name}.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


@pytest.mark.parametrize("locale", [EN, ZH], ids=["en-US", "zh-TW"])
@pytest.mark.parametrize("name", ["top-money", "top-cost"])
async def test_board(cog: Economy, store: Store, name: str, locale: discord.Locale) -> None:
    """Requirement: Administrators see the boards."""
    await give(store)
    interaction = run(name, locale=locale)

    await cog.show_board(interaction.as_interaction())

    assert edited(interaction) == ("", [GOLDEN["boards"][name][locale.value]])


async def test_empty_board(cog: Economy, store: Store) -> None:
    """Requirement: Administrators see the boards."""
    interaction = run("top-cost")

    await cog.show_board(interaction.as_interaction())

    board = dict(GOLDEN["boards"]["top-cost"]["en-US"])
    del board["description"]
    assert edited(interaction) == ("", [board])
    assert await store.keys(NAMESPACE) == []  # v3 created the guild's file


async def test_operator_template(store: Store, tmp_path: Path) -> None:
    """Requirement: Administrators see the boards."""
    # As v3's setEmbeds: the rows replace the first embed's description, the user's values fill
    # them, the other embeds go and the content stays.
    operator_template(
        tmp_path / "plugins",
        "en-US",
        "top-money",
        """\
        content: "Board for %user_name%"
        embeds:
          - title:
              text: "Board"
            description: "%index%. %name_mention% %economy_board% for %user_name%\\n"
          - title:
              text: "Dropped"
        """,
    )
    bot = await load_plugin("Economy", tmp_path / "plugins", store, config=CONFIG)
    cog = cast("Economy", bot.get_cog("Economy"))
    await give(store)
    interaction = run("top-money")

    await cog.show_board(interaction.as_interaction())

    rows = "1. <@2> 50 for admin\n2. <@1> 20 for admin\n3. <@3> 20 for admin\n"
    assert edited(interaction) == ("Board for admin", [{"title": "Board", "description": rows}])


@pytest.mark.parametrize(
    "text",
    [
        'embeds:\n  - title:\n      text: "Board"\n',
        'content: "Board"\n',
        'embeds:\n  - model_key: "board"\n    description: "%index%"\n',
    ],
    ids=["no-description", "no-embed", "model"],
)
async def test_missing_row_template(
    text: str, store: Store, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Board templates are checked at load."""
    path = operator_template(tmp_path / "plugins", "zh-TW", "top-cost", text)

    bot = await load_plugin("Economy", tmp_path / "plugins", store, config=CONFIG)

    assert bot.loaded == ()
    assert f"{path}: " in caplog.text
