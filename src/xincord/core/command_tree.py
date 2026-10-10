"""The command tree: ephemeral auto-defer, command scopes, and uploads only when commands change.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/logger/InteractionLogger.kt:25-41
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/ListenerManager.kt:18-36
"""

import hashlib
import json
import logging
from typing import TYPE_CHECKING, Any, override

import discord
from discord import app_commands

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xincord.core.storage import Store

type Payload = dict[str, Any]

logger = logging.getLogger(__name__)

NAMESPACE = "core"  # store namespace of the upload hashes


class CommandTree(app_commands.CommandTree[discord.Client]):
    """discord.py's command tree with v3's ephemeral defer and change-based uploads."""

    @override
    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        """Defer application commands ephemerally unless they set ``extras["defer"]`` to False."""
        command = interaction.command
        if (
            interaction.type is discord.InteractionType.application_command
            and command is not None
            and command.extras.get("defer", True)
        ):
            await interaction.response.defer(ephemeral=True, thinking=True)
        return True

    async def payloads(self, guild_id: int | None = None) -> tuple[list[Payload], list[Payload]]:
        """Return the payloads of the global commands and of the guild commands, translated."""
        if guild_id is not None:
            raise NotImplementedError
        global_payload: list[Payload] = []
        guild_payload: list[Payload] = []
        for command in self.get_commands():
            payload = (
                command.to_dict(self)
                if self.translator is None
                else await command.get_translated_payload(self, self.translator)
            )
            (global_payload if command.extras.get("global") else guild_payload).append(payload)
        return global_payload, guild_payload

    async def sync_global(self, store: Store, *, force: bool = False) -> bool:
        """Upload the global commands if they changed since the last upload, or if forced.

        Returns:
            Whether they were uploaded. A failed upload is logged and returns False.

        Raises:
            MissingApplicationID: The client has not logged in.
        """
        application_id = self._application_id()
        payload, _ = await self.payloads()
        http = self.client.http
        return await self._upload(
            store,
            "global",
            payload,
            lambda: http.bulk_upsert_global_commands(application_id, payload=payload),
            force=force,
        )

    async def sync_guild(self, store: Store, guild_id: int, *, force: bool = False) -> bool:
        """Upload the guild commands to ``guild_id`` if they changed there, or if forced.

        Returns:
            Whether they were uploaded. A failed upload is logged and returns False.

        Raises:
            MissingApplicationID: The client has not logged in.
        """
        application_id = self._application_id()
        _, payload = await self.payloads()
        http = self.client.http
        return await self._upload(
            store,
            f"guild:{guild_id}",
            payload,
            lambda: http.bulk_upsert_guild_commands(application_id, guild_id, payload=payload),
            force=force,
        )

    def _application_id(self) -> int:
        if (application_id := self.client.application_id) is None:
            raise app_commands.MissingApplicationID
        return application_id

    async def _upload(
        self,
        store: Store,
        scope: str,
        payload: list[Payload],
        send: Callable[[], Awaitable[object]],
        *,
        force: bool,
    ) -> bool:
        key = f"commands:{scope}"
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(text.encode()).hexdigest()
        if not force and await store.get(NAMESPACE, key) == digest:
            return False
        try:
            await send()
        except discord.HTTPException:
            logger.exception("Uploading the %s commands failed", scope)
            return False
        await store.put(NAMESPACE, key, digest)
        return True
