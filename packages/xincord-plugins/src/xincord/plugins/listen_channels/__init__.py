"""Listen channels: the per-channel settings that VoiceLogger and ChatLogger share.

A listen channel is where an administrator ran a plugin's settings command; it gets the plugin's
logs of the channels its settings detect. v3 copied this code between the two plugins
(``ChannelData``, ``JsonManager`` and the settings menu). This package is no plugin: it has no
entry point, both plugins import it, and neither needs the other.
"""
