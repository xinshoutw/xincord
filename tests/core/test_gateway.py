"""Gateway events that discord.py does not parse reach the plugins' listeners.

discord.py 2.7.1 drops ``VOICE_CHANNEL_STATUS_UPDATE``, which v3's VoiceLogger handled through
JDA's ``ChannelUpdateVoiceStatusEvent``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/Event.kt:101-104
"""

from typing import TYPE_CHECKING

import pytest

from plugin_fakes import gateway, parsers
from xincord.core.bot import Bot

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.storage import Store

STATUS = "VOICE_CHANNEL_STATUS_UPDATE"
PAYLOAD: dict[str, object] = {"id": "30", "guild_id": "10", "status": "Gaming"}


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Plugins receive gateway events that discord.py does not parse",
)
async def test_unparsed_event(store: Store, tmp_path: Path) -> None:
    """Requirement: Plugins receive gateway events that discord.py does not parse."""
    bot = Bot([], root=tmp_path, store=store)
    received: list[object] = []

    async def listener(payload: dict[str, object]) -> None:
        received.append(payload)

    bot.add_listener(listener, "on_gateway_voice_channel_status_update")

    bot.relay_gateway_event(STATUS)
    bot.relay_gateway_event(STATUS)  # a reloaded plugin relays it again
    await gateway(bot, STATUS, PAYLOAD)

    assert received == [PAYLOAD]


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Plugins receive gateway events that discord.py does not parse",
)
async def test_parsed_event(store: Store, tmp_path: Path) -> None:
    """Requirement: Plugins receive gateway events that discord.py does not parse."""
    bot = Bot([], root=tmp_path, store=store)
    calls: list[tuple[str, object]] = []
    # Stands for a parser of discord.py's, as a later version may add one for the event.
    parsers(bot)["XINCORD_TEST"] = lambda payload: calls.append(("discord.py", payload))

    async def listener(payload: dict[str, object]) -> None:
        calls.append(("listener", payload))

    bot.add_listener(listener, "on_gateway_xincord_test")

    bot.relay_gateway_event("XINCORD_TEST")
    await gateway(bot, "XINCORD_TEST", PAYLOAD)

    assert calls == [("discord.py", PAYLOAD), ("listener", PAYLOAD)]
