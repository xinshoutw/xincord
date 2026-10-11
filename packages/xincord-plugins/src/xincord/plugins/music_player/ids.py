"""The panels' button IDs.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/MusicPlayer/src/main/kotlin/musicplayer/MusicPlayer.kt:58-63
"""

from xincord.core.component_ids import ComponentIds

# v3's only field and its derived prefix (the lowercase plugin name and `@`), so that v3's panels
# keep working: musicplayer@a:skip. New panels: music_player:1:a=skip.
IDS = ComponentIds("music_player", ("action",), legacy_prefix="musicplayer@")
