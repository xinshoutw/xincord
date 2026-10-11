"""The panels' button IDs."""

from xincord.core.component_ids import ComponentIds

# The legacy field and prefix (the lowercase plugin name and `@`), so that legacy panels keep
# working: musicplayer@a:skip. New panels: music_player:1:a=skip.
IDS = ComponentIds("music_player", ("action",), legacy_prefix="musicplayer@")
