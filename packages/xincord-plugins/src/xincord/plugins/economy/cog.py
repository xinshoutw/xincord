"""The wallet commands, the boards and v3's balance button.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/Economy.kt:18-203
    XsDiscordBotKt@3a59607:Plugins/Economy/src/main/kotlin/economy/MessageReplier.kt:13-69
"""

from typing import TYPE_CHECKING

from discord.ext import commands

from xincord.core.placeholders import actor_values, global_values
from xincord.core.templates import render_message

from .store import change, read
from .wallet import OPERATIONS

if TYPE_CHECKING:
    import discord

    from xincord.core.i18n import Lang
    from xincord.core.storage import Store
    from xincord.core.templates import Message, Templates

    from .config import Config
    from .wallet import Wallet

BAD_VALUE = "Bad Value"  # v3's reply to a negative amount, the same in every locale


class Economy(commands.Cog):
    """The plugin's state and handlers; ``setup`` registers them."""

    def __init__(self, config: Config, store: Store, lang: Lang, templates: Templates) -> None:
        """Keep the store and what ``setup`` loaded."""
        self.config = config
        self.store = store
        self.lang = lang
        self.templates = templates

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
        values = _user_values(interaction, target) | wallet_values(wallet)
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
        values = _user_values(interaction, member) | wallet_values(after)
        values |= {
            "economy_money_before": str(before.money),
            "economy_cost_before": str(before.cost),
        }
        await self._reply(interaction, name, values)

    async def show_board(self, interaction: discord.Interaction) -> None:
        """Stub."""
        raise NotImplementedError

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


def _command_name(interaction: discord.Interaction) -> str:
    """The base name of the invoked command, which picks the change, the board or the template."""
    return interaction.command.name if interaction.command else ""


def _user_values(
    interaction: discord.Interaction, user: discord.Member | discord.User
) -> dict[str, str]:
    """v3's ``Placeholder.get(user)``: the user's keys and the bot's."""
    bot = interaction.client.user
    return {} if bot is None else actor_values(user, bot)


def wallet_values(wallet: Wallet) -> dict[str, str]:
    """The wallet's keys, v3's ``economy_money`` and ``economy_cost``."""
    return {"economy_money": str(wallet.money), "economy_cost": str(wallet.cost)}
