"""The wallet commands, the boards and v3's balance button."""

from dataclasses import replace
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, cast

import discord
from discord import app_commands
from discord.ext import commands

from xincord.core.component_ids import ComponentIds
from xincord.core.placeholders import actor_values, global_values, render
from xincord.core.templates import TemplateError, render_message

from .store import change, read, read_all
from .wallet import OPERATIONS, rank

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xincord.core.component_ids import ParsedId
    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Message, MessageTemplate, Templates

    from .config import Config
    from .wallet import Kind, Wallet

# v3 declared no fields and only checked its prefix; a codec needs one field, and v3's plugins
# start with the action.
IDS = ComponentIds("economy", ("action",), legacy_prefix="economy@")
BAD_VALUE = "Bad Value"  # v3's reply to a negative amount, the same in every locale
# v3's boards and what each ranks.
BOARDS: dict[str, Kind] = {"top-money": "money", "top-cost": "cost"}


class CommandSpec(NamedTuple):
    """One of v3's commands: the handler that serves it and v3's base texts."""

    kind: Literal["balance", "board", "change"]
    description: str
    member: str = ""  # the member option's description, if it has the option
    value: str = ""  # the value option's description, if it has the option


MODIFY = "Specify the member to modify."
# v3's commands, in v3's order, with the texts of Register.kt.
COMMANDS = {
    "balance": CommandSpec(
        "balance", "Get current money from member", "Specify the member to query."
    ),
    "top-money": CommandSpec("board", "Get leaderboard for money"),
    "top-cost": CommandSpec("board", "Get leaderboard from log money"),
    "add-money": CommandSpec(
        "change", "Add money to member's balance", MODIFY, "Specify the amount to add."
    ),
    "remove-money": CommandSpec(
        "change", "Remove money from member's balance", MODIFY, "Specify the amount to remove."
    ),
    "set-money": CommandSpec(
        "change", "Set money to member's balance", MODIFY, "Specify the new balance."
    ),
    "add-cost": CommandSpec(
        "change", "Add money log to member", MODIFY, "Specify the amount to add."
    ),
    "remove-cost": CommandSpec(
        "change", "Remove money log to member", MODIFY, "Specify the amount to remove."
    ),
    "set-cost": CommandSpec(
        "change", "Set money log to member", MODIFY, "Specify the new balance."
    ),
}


class Economy(commands.Cog):
    """The plugin's state and handlers; ``setup`` registers them."""

    def __init__(self, config: Config, store: Store, lang: Lang, templates: Templates) -> None:
        """Keep the store and what ``setup`` loaded."""
        self.config = config
        self.store = store
        self.lang = lang
        self.templates = templates

    def command(self, name: str) -> app_commands.Command[Any, ..., None]:
        """Build v3's command ``name``, localized from ``register.yaml``.

        ``balance`` is for everyone, as v3's ``DefaultMemberPermissions.ENABLED``; Discord shows
        the others to administrators by default, and their handlers check ``admin_id``, as in v3.
        """
        lang, spec = self.lang, COMMANDS[name]
        command: app_commands.Command[Any, ..., None]
        label = lang.command(name, f"{name}.name")
        description = lang.command(spec.description, f"{name}.description")
        if spec.kind == "balance":
            command = app_commands.Command(
                name=label, description=description, callback=self.show_balance
            )
        elif spec.kind == "board":
            command = app_commands.Command(
                name=label, description=description, callback=self.show_board
            )
        else:
            command = app_commands.Command(
                name=label, description=description, callback=self.change_wallet
            )
        # One call each: describe gives every option it does not name an ellipsis as its text.
        options = {
            key: text for key, text in (("member", spec.member), ("value", spec.value)) if text
        }
        app_commands.rename(
            **{key: lang.command(key, f"{name}.options.{key}.name") for key in options}
        )(command)
        app_commands.describe(
            **{
                key: lang.command(text, f"{name}.options.{key}.description")
                for key, text in options.items()
            }
        )(command)
        if spec.kind == "balance":
            return command
        return app_commands.default_permissions(administrator=True)(command)

    async def show_balance(
        self,
        interaction: discord.Interaction,
        member: discord.Member | discord.User | None = None,
    ) -> None:
        """Show the user's wallet, or ``member``'s to an administrator (v3's ``/balance``).

        ``member`` is a user option, as v3's ``asUser``: users outside the guild count. A user whom
        ``admin_id`` does not list and who names someone else gets ``no-permission``, where v3
        silently showed their own wallet. Reading writes nothing; v3 created the wallet.
        """
        guild = interaction.guild
        if guild is None:  # guild commands run in guilds only, as v3's guard assumed
            return
        target = member or interaction.user
        if target.id != interaction.user.id and not self._is_admin(interaction):
            await self._no_permission(interaction)
            return
        wallet = await read(self.store, guild.id, target.id)
        values = _user_values(interaction, target) | _wallet_values(wallet)
        await self._reply(interaction, "balance", values)

    async def change_wallet(
        self, interaction: discord.Interaction, member: discord.Member | discord.User, value: int
    ) -> None:
        """Change ``member``'s wallet by ``value`` as the invoked command does (v3's six commands).

        As in v3, a user whom ``admin_id`` does not list gets ``no-permission`` before the value is
        looked at, and a negative value gets ``Bad Value``; 0 is a change. The reply is the message
        named like the command, with ``member``'s values and the amounts before and after.
        """
        guild = interaction.guild
        if guild is None:  # guild commands run in guilds only, as v3's guard assumed
            return
        if not self._is_admin(interaction):
            await self._no_permission(interaction)
            return
        if value < 0:
            await interaction.edit_original_response(content=BAD_VALUE)
            return
        name = _command_name(interaction)
        before, after = await change(self.store, guild.id, member.id, OPERATIONS[name], value)
        values = _user_values(interaction, member) | _wallet_values(after)
        values |= {
            "economy_money_before": str(before.money),
            "economy_cost_before": str(before.cost),
        }
        await self._reply(interaction, name, values)

    async def show_board(self, interaction: discord.Interaction) -> None:
        """Show the guild's money or cost board to an administrator (v3's two board commands).

        As in v3, a user whom ``admin_id`` does not list gets ``no-permission``, and the board is
        the message named like the command, rendered with the user's values (v3's
        ``Placeholder.get(event.user)``). Nothing is written; v3 created the guild's file.
        """
        guild = interaction.guild
        if guild is None:  # guild commands run in guilds only, as v3's guard assumed
            return
        if not self._is_admin(interaction):
            await self._no_permission(interaction)
            return
        name = _command_name(interaction)
        wallets = await read_all(self.store, guild.id)
        ranked = rank(wallets, BOARDS[name], self.config.board_user_show_limit)
        template = self.templates.message(name, interaction.locale.value)
        values = _user_values(interaction, interaction.user)
        await _edit(interaction, _board(template, values, ranked))

    async def handle(self, interaction: discord.Interaction, _parsed: ParsedId) -> None:
        """Show the presser's wallet for a button with an Economy ID; ``setup`` routes them here.

        v3 checked only the ``economy@`` prefix, so the ID's fields do not matter. As in v3's
        ``deferReply(true)``, the response is deferred ephemerally and then shows ``balance``;
        other components, modals and presses outside a guild get no answer. Reading writes nothing;
        v3 created the wallet.
        """
        guild = interaction.guild
        # Only button presses carry this type: v3 left selects and modals unanswered.
        kind = cast("Mapping[str, object]", interaction.data or {}).get("component_type")
        if guild is None or kind != discord.ComponentType.button.value:
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        wallet = await read(self.store, guild.id, interaction.user.id)
        values = _user_values(interaction, interaction.user) | _wallet_values(wallet)
        await self._reply(interaction, "balance", values)

    def _is_admin(self, interaction: discord.Interaction) -> bool:
        """Whether ``admin_id`` lists the user; Discord's Administrator does not count."""
        return interaction.user.id in self.config.admin_id

    async def _no_permission(self, interaction: discord.Interaction) -> None:
        """Answer ``no-permission``, which v3 rendered with its global placeholders only."""
        await self._reply(interaction, "no-permission", global_values(interaction.client))

    async def _reply(
        self, interaction: discord.Interaction, name: str, values: dict[str, str]
    ) -> None:
        """Edit the deferred response into the message ``name``, in the user's locale, as v3."""
        message = self.templates.message(name, interaction.locale.value)
        await _edit(interaction, render_message(message, values))


async def _edit(interaction: discord.Interaction, message: Message) -> None:
    """Replace the response that the command tree deferred ephemerally, as v3's core did."""
    await interaction.edit_original_response(
        content=message.content, embeds=message.embeds, view=message.view, attachments=message.files
    )


def check_boards(lang: Lang, templates: Templates) -> None:
    """Check that each locale's board templates hold the template of the board's rows.

    The rows come from the first embed's description, as in v3, which threw at each use without
    one; here the plugin does not load.

    Raises:
        TemplateError: A board template has no first embed with a description, or it is a model.
    """
    for locale in lang.locales:
        for name in BOARDS:
            embeds = templates.message(name, locale).embeds
            if not embeds or embeds[0].model_key is not None or not embeds[0].description:
                path = lang.template(f"message/{name}", locale)
                msg = f"{path}: the first embed needs a description, the template of the rows"
                raise TemplateError(msg)


def _board(
    template: MessageTemplate, values: dict[str, str], ranked: list[tuple[int, int]]
) -> Message:
    """Render a board: one row per ranked wallet in the first embed, the only embed kept.

    Each row renders the first embed's description with ``values`` and v3's ``index``,
    ``name_mention`` and ``economy_board``; the rows replace that description, and the message keeps
    only that embed, as v3's ``setEmbeds``. Without rows the embed has no description, as in v3.
    """
    row = template.embeds[0].description or ""  # check_boards made sure it is there
    rows = "".join(
        render(
            row,
            values
            | {
                "index": str(index),
                "name_mention": f"<@{user_id}>",
                "economy_board": str(amount),
            },
        )
        for index, (user_id, amount) in enumerate(ranked, start=1)
    )
    message = render_message(template, values)
    board = message.embeds[0].copy() if message.embeds else discord.Embed()
    board.description = rows or None
    return replace(message, embeds=(board,))


def _command_name(interaction: discord.Interaction) -> str:
    """The base name of the invoked command, which picks the change, the board or the template."""
    return interaction.command.name if interaction.command else ""


def _user_values(
    interaction: discord.Interaction, user: discord.Member | discord.User
) -> dict[str, str]:
    """v3's ``Placeholder.get(user)``: the user's keys and the bot's."""
    bot = interaction.client.user
    return {} if bot is None else actor_values(user, bot)


def _wallet_values(wallet: Wallet) -> dict[str, str]:
    """The wallet's keys, v3's ``economy_money`` and ``economy_cost``."""
    return {"economy_money": str(wallet.money), "economy_cost": str(wallet.cost)}
