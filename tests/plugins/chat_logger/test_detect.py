"""Which channels a listen channel's settings detect, threads included, and where an event goes.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/ChannelData.kt:31-46
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/ChatLogger.kt:132-138
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/ChatLogger.kt:174-180
"""

import pytest

from xincord.plugins.listen_channels.settings import ChannelIds, Setting, detects, targets

# Channels and threads as (ID, then what holds them): channel 30 of category 22, 31 of category
# 20, 32 of category 21 and 33 outside categories; threads 40, 41 and 42 of channels 30, 31 and 32.
PLACES: dict[int, ChannelIds] = {
    30: (30, 22),
    31: (31, 20),
    32: (32, 21),
    33: (33, None),
    40: (40, 30, 22),
    41: (41, 31, 20),
    42: (42, 32, 21),
}


def detected(setting: Setting) -> list[int]:
    """The channels and threads of ``PLACES`` that ``setting`` detects."""
    return [channel for channel, place in PLACES.items() if detects(setting, *place)]


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Listen channels detect message channels"
)
def test_allow_mode() -> None:
    """Requirement: Listen channels detect message channels."""
    setting = Setting(allow_mode=True, allow=(30, 20), block=(31, 32))  # the block list is unused

    # A thread counts as its parent channel and that channel's category; v3 never forwarded a
    # thread's edits and deletions.
    assert detected(setting) == [30, 31, 40, 41]


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Listen channels detect message channels"
)
def test_block_mode() -> None:
    """Requirement: Listen channels detect message channels."""
    setting = Setting(allow_mode=False, allow=(32,), block=(30, 20))  # the allow list is unused

    # v3's block mode took the guild's channels, which leave threads out.
    assert detected(setting) == [32, 33, 42]


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Listen channels detect message channels"
)
def test_a_thread_on_its_own() -> None:
    """Requirement: Listen channels detect message channels."""
    # v3's select menus offered threads; the allow list can hold one.
    assert detected(Setting(allow=(42,))) == [42]
    assert detected(Setting(allow_mode=False, block=(42,))) == [30, 31, 32, 33, 40, 41]


@pytest.mark.xfail(
    strict=True, raises=NotImplementedError, reason="Listen channels detect message channels"
)
def test_every_detecting_listen_channel() -> None:
    """Requirement: Listen channels detect message channels."""
    settings = {
        7: Setting(allow_mode=False, block=(32,)),
        5: Setting(allow=(21,)),
        6: Setting(allow=(42,)),
        8: Setting(allow=(30,)),
    }

    assert targets(settings, [PLACES[42]]) == [5, 6]  # in stored order
    assert targets(settings, [PLACES[30]]) == [7, 8]
