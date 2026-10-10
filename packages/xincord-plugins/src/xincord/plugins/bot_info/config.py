"""The plugin's ``config.yaml``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/BotInfo/src/main/kotlin/botinfo/config/ConfigSerializer.kt:5-8
"""

from typing import Annotated

from pydantic import StringConstraints

from xincord.core.config import Model

SOURCE_URL = "https://github.com/xinshoutw/xincord"  # the default source link: this repository
# Discord's limit for a link button's URL, the strictest place a template can put the link.
URL_MAX = 512

# Checked when the plugin loads, so that a typo disables it with an error that names the key
# instead of showing a broken link or making Discord refuse the reply.
SourceUrl = Annotated[str, StringConstraints(pattern=r"^https?://\S+$", max_length=URL_MAX)]


class Config(Model):
    """``plugins/BotInfo/config.yaml``; the bundled ``config.yaml`` holds the same defaults.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin.
    """

    # The link to the bot's source code that /bot-info shows (decision C3, AGPL section 13).
    source_url: SourceUrl = SOURCE_URL
