"""What the plugin logs: URLs as their origins, and failures when they start, change or end.

The owner decided on 2026-10-10 that logs show only a listener's scheme, host and port, since the
path or the query of a push URL carries the monitor's push token (v3 logged whole URLs), and that a
listener failing at every push must not log at every push (v3 did).

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/IntervalPusher/src/main/kotlin/intervalpusher/IntervalPusher.kt:99-123
"""

import re
from dataclasses import dataclass, field

from yarl import URL

AUTHORITY_END = re.compile(r"[/?#]")  # where the path, the query or the fragment begins
# An http or https URL in an error's text, up to the next whitespace: aiohttp's connect timeout
# names the whole URL, and its error for a malformed answer ends with it in quotes.
URL_IN_TEXT = re.compile(r"\bhttps?://\S+", re.IGNORECASE)
QUOTES = "'\""
HIDDEN = "..."  # what stands for a private part of a URL in an error's text
STEADY = 3  # successes in a row that end a failure episode


def origin(url: str) -> str:
    """The scheme, the host and the port of ``url``: what the logs show of it.

    The user info, the path, the query and the fragment are left out, since they can carry the push
    token. String operations only, so that no URL makes it raise: ``urlsplit(...).port`` raises for
    a port that ``%ping%`` replaced with ``-1``.
    """
    scheme, _, rest = url.partition("://")
    authority = AUTHORITY_END.split(rest, maxsplit=1)[0]
    return f"{scheme.lower()}://{authority.rpartition('@')[2]}"


def private_parts(url: str) -> tuple[str, ...]:
    """What logs must not show of ``url``, longest first: user info, path, query and fragment.

    The path, the query and the fragment count together, without the fragment, and each alone, as
    written and as yarl encodes them, which is what aiohttp sends; a part of one character (a bare
    ``/``) says nothing and is left.
    """
    parts: set[str] = set()
    for form in _forms(url):
        rest = form.partition("://")[2]
        authority = AUTHORITY_END.split(rest, maxsplit=1)[0]
        tail = rest[len(authority) :]
        request, _, fragment = tail.partition("#")
        path, _, query = request.partition("?")
        parts |= {authority.rpartition("@")[0], tail, request, path, query, fragment}
    return tuple(sorted((part for part in parts if len(part) > 1), key=_longest_first))


def _forms(url: str) -> tuple[str, ...]:
    """``url`` as written and as yarl encodes it; yarl refuses some (a port that is ``-1``)."""
    try:
        return (url, str(URL(url)))
    except ValueError:
        return (url,)


def _longest_first(part: str) -> tuple[int, str]:
    return (-len(part), part)


def redact(text: str, *urls: str) -> str:
    """``text`` with each http or https URL in it cut to its origin, and the private parts of
    ``urls`` replaced wherever they appear.

    The whole run of non-space characters goes, so that a quote inside a path leaves nothing of it
    behind; the quotes that end the run stay, so that ``url='...'`` stays quoted.
    """
    text = URL_IN_TEXT.sub(_cut, text)
    parts = {part for url in urls for part in private_parts(url)}
    for part in sorted(parts, key=_longest_first):
        text = text.replace(part, HIDDEN)
    return text


def _cut(match: re.Match[str]) -> str:
    found = match[0]
    url = found.rstrip(QUOTES)
    return origin(url) + found[len(url) :]


@dataclass
class Failures:
    """One step of a listener (its pushes, or its pings) and its failure episode, if one is open.

    An episode starts with a failure and ends once the step has worked ``STEADY`` times in a row.
    Only a failure whose kind (a status code or an error type) is new in the episode is logged at
    its level, so that a listener that fails at every push, alternates two kinds of failure or
    fails at every other push does not log at every push; the others go to the debug level.
    """

    kinds: set[object] = field(default_factory=set[object])  # the kinds logged in the episode
    count: int = 0  # the episode's failures; 0 while none is open
    streak: int = 0  # the successes in a row since the episode's last failure

    def fail(self, kind: object) -> bool:
        """Count a failure of ``kind``; return whether its kind is new in the episode."""
        self.count += 1
        self.streak = 0
        if kind in self.kinds:
            return False
        self.kinds.add(kind)
        return True

    def succeed(self) -> int:
        """Count a success; return the episode's failures when this success ends it, else 0."""
        if not self.count:
            return 0
        self.streak += 1
        if self.streak < STEADY:
            return 0
        count = self.count
        self.kinds = set()
        self.count = 0
        self.streak = 0
        return count
