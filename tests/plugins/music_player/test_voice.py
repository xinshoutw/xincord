"""``/join`` and ``/disconnect``: the bot in the member's voice channel, and out of it.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:335-363
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/util/MusicPlayerUtils.kt:85-109
"""

from typing import TYPE_CHECKING

import pytest

from music_fakes import song, text
from xincord.plugins.music_player.history import Entry, Requester

if TYPE_CHECKING:
    from conftest import Scene

VOICE, STAGE, LOCKED, FULL, OTHER = 20, 21, 22, 23, 24
ALICE = Requester(1, "Alice", "alice", "https://cdn.example/alice.png")
DELETED: tuple[str, dict[str, object]] = ("delete_original_response", {})


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Members bring the bot into voice and send it away",
)
async def test_join(scene: Scene) -> None:
    """Requirement: Members bring the bot into voice and send it away."""
    interaction = scene.who(VOICE)

    await scene.cog.join_voice(interaction.as_interaction())

    assert scene.link.connects == [(10, VOICE)]
    assert interaction.sent == [DELETED]  # as v3: no confirmation


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Members bring the bot into voice and send it away",
)
async def test_join_moves_the_bot(scene: Scene) -> None:
    """Requirement: Members bring the bot into voice and send it away."""
    await scene.connect(OTHER)
    interaction = scene.who(VOICE)

    await scene.cog.join_voice(interaction.as_interaction())

    assert scene.link.connects == [(10, OTHER)]
    assert scene.guild.voice_moves == [VOICE]  # JDA's openAudioConnection moved the bot
    assert interaction.sent == [DELETED]


@pytest.mark.parametrize(
    ("channel", "key"),
    [
        pytest.param(None, "join-voice-first", id="outside voice"),
        pytest.param(STAGE, "voice-channel-not-found", id="stage"),
        pytest.param(LOCKED, "cannot-connect", id="no Connect"),
        pytest.param(FULL, "cannot-connect", id="full"),
    ],
)
@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Members bring the bot into voice and send it away",
)
async def test_join_refused(scene: Scene, channel: int | None, key: str) -> None:
    """Requirement: Members bring the bot into voice and send it away."""
    interaction = scene.who(channel)

    await scene.cog.join_voice(interaction.as_interaction())

    assert interaction.sent == [("edit_original_response", {"content": text(key)})]
    assert scene.link.connects == []


@pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="Members bring the bot into voice and send it away",
)
async def test_disconnect(scene: Scene) -> None:
    """Requirement: Members bring the bot into voice and send it away."""
    await scene.connect(VOICE)
    await scene.cog.sessions[10].enqueue([Entry(song(1), ALICE)])
    leave = scene.who(None)  # any member, even outside voice, as in v3
    again = scene.who(None)

    await scene.cog.leave_voice(leave.as_interaction())
    await scene.cog.leave_voice(again.as_interaction())

    assert scene.link.disconnects == [10]
    assert scene.cog.sessions[10].history.entries == []
    assert leave.sent[0] == DELETED
    assert again.sent[-1] == ("edit_original_response", {"content": text("not-connected")})
