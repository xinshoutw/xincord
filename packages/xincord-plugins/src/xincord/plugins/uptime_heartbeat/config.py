"""The plugin's ``config.yaml``.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/config/ConfigSerializer.kt:5-15
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:61-123
"""

from typing import Annotated
from urllib.parse import urlsplit

from pydantic import AfterValidator, Field

from xincord.core.config import Model

PING = "%ping%"  # the URL's only placeholder: the REST ping, replaced before each push
# v3's Int refused larger values at load; v3 also took 0 and negatives, which made the loop push
# without pause.
MAX_INTERVAL = 2_147_483_647
SCHEMES = frozenset({"http", "https"})


def _push_url(url: str) -> str:
    """Accept ``url`` if it is an http or https URL with a host once ``%ping%`` is a number.

    v3 took any string and failed at every push; checked here, a typo names the key at load.
    """
    try:
        parts = urlsplit(url.replace(PING, "0"))
        _ = parts.port  # raises ValueError unless the port is a number from 0 to 65535
    except ValueError as error:
        msg = f"not a URL: {error}"
        raise ValueError(msg) from error
    if parts.scheme not in SCHEMES or not parts.hostname or any(c.isspace() for c in url):
        msg = "must be an http or https URL with a host and no spaces"
        raise ValueError(msg)
    return url


class Listener(Model):
    """A URL to push and the delay between pushes, with v3's keys."""

    url: Annotated[str, AfterValidator(_push_url)]
    interval: Annotated[int, Field(ge=1, le=MAX_INTERVAL)]  # seconds after each attempt


class Config(Model):
    """``plugins/UptimeHeartbeat/config.yaml``; the bundled ``config.yaml`` lists no listeners.

    v3's ``enabled`` key is gone: the core config's ``plugins`` list enables the plugin.
    """

    listeners: tuple[Listener, ...]  # required, as in v3
