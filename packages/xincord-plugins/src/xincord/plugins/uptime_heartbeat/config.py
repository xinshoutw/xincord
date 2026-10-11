"""The plugin's ``config.yaml``."""

from typing import Annotated
from urllib.parse import urlsplit

from pydantic import AfterValidator, ConfigDict, Field

from xincord.core.config import Model

PING = "%ping%"  # the URL's only placeholder: the REST ping, replaced before each push
# A positive 32-bit integer: 0 or a negative interval would push without pause.
MAX_INTERVAL = 2_147_483_647
SCHEMES = frozenset({"http", "https"})


def _push_url(url: str) -> str:
    """Accept ``url`` if it is an http or https URL with a host once ``%ping%`` is a number.

    Checked at load, so that a typo names the key instead of failing every push. The errors
    never quote the URL, whose path, query or user info can hold the push token or a
    password.
    """
    try:
        parts = urlsplit(url.replace(PING, "0"))
        _ = parts.port  # raises ValueError unless the port is a number from 0 to 65535
    except ValueError:
        # urlsplit's errors quote parts of the URL, such as the text after the last ":".
        msg = "not a URL: its host or port cannot be read"
        raise ValueError(msg) from None
    if parts.scheme not in SCHEMES or not parts.hostname or any(c.isspace() for c in url):
        msg = "must be an http or https URL with a host and no spaces"
        raise ValueError(msg)
    return url


class Listener(Model):
    """A URL to push and the delay between pushes."""

    # pydantic's errors show no input: the core logs them with their traceback.
    model_config = ConfigDict(hide_input_in_errors=True)

    url: Annotated[str, AfterValidator(_push_url)]
    interval: Annotated[int, Field(ge=1, le=MAX_INTERVAL)]  # seconds after each attempt


class Config(Model):
    """``plugins/UptimeHeartbeat/config.yaml``; the bundled ``config.yaml`` lists no listeners.

    The core config's ``plugins`` list enables the plugin; an ``enabled`` key here only warns.
    """

    model_config = ConfigDict(hide_input_in_errors=True)  # no URL in the errors, as in Listener

    listeners: tuple[Listener, ...]  # required
