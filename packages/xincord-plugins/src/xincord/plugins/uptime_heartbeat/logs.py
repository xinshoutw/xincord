"""What the plugin's log lines show of a URL: its origin, never the push token.

The owner decided on 2026-10-10 that logs show only a listener's scheme, host and port: the path or
the query of a push URL carries the monitor's push token (v3 logged whole URLs).

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:99-123
"""


def origin(url: str) -> str:
    """The scheme, the host and the port of ``url``: what the logs show of it."""
    raise NotImplementedError


def redact(text: str) -> str:
    """``text`` with each http or https URL in it cut to its origin."""
    raise NotImplementedError
