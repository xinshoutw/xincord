"""Which voice channels a listen channel's settings detect, and where an event goes.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/ChannelData.kt:31-46
    XsDiscordBotKt@3a59607:Plugins/VoiceLogger/src/main/kotlin/logger/voice/VoiceLogger.kt:278-350
"""

from xincord.plugins.listen_channels.settings import Setting, detects, targets

# Voice channels as (ID, category ID): 30 of category 22, 31 of category 20, 32 of category 21
# and 33 outside categories.
CHANNELS = {30: 22, 31: 20, 32: 21, 33: None}


def test_allow_mode() -> None:
    """Requirement: Listen channels detect voice channels."""
    setting = Setting(allow_mode=True, allow=(30, 20), block=(31, 32))  # the block list is unused

    detected = [
        channel for channel, category in CHANNELS.items() if detects(setting, channel, category)
    ]

    assert detected == [30, 31]


def test_block_mode() -> None:
    """Requirement: Listen channels detect voice channels."""
    setting = Setting(allow_mode=False, allow=(32,), block=(30, 20))  # the allow list is unused

    detected = [
        channel for channel, category in CHANNELS.items() if detects(setting, channel, category)
    ]

    assert detected == [32, 33]


def test_empty_lists() -> None:
    """Requirement: Listen channels detect voice channels."""
    # A channel without settings detects nothing; the block mode with nothing blocked, everything.
    assert not any(detects(Setting(), channel, category) for channel, category in CHANNELS.items())
    everything = Setting(allow_mode=False)
    assert all(detects(everything, channel, category) for channel, category in CHANNELS.items())


def test_either_side_of_a_switch() -> None:
    """Requirement: Listen channels detect voice channels."""
    settings = {
        7: Setting(allow=(31,)),
        5: Setting(allow=(30,)),
        6: Setting(allow_mode=False, block=(30, 22, 31)),
    }

    assert targets(settings, [(30, 22), (32, 21)]) == [5, 6]  # in stored order
    assert targets(settings, [(30, 22)]) == [5]
    assert targets(settings, []) == []
