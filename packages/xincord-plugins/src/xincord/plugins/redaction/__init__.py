"""URLs in logs and error texts: their origins only, since their paths can carry secrets.

UptimeHeartbeat's push URLs carry the monitor's push token, and a webhook's URL carries the
webhook's token (Ticket's archive). The owner decided on 2026-10-10 that logs show only a URL's
scheme, host and port. This package is no plugin: it has no entry point, and the plugins that use
it import it.
"""

import re

from yarl import URL

AUTHORITY_END = re.compile(r"[/?#]")  # where the path, the query or the fragment begins
# An http or https URL in an error's text, up to the next whitespace: aiohttp's connect timeout
# names the whole URL, and its error for a malformed answer ends with it in quotes.
URL_IN_TEXT = re.compile(r"\bhttps?://\S+", re.IGNORECASE)
QUOTES = "'\""
HIDDEN = "..."  # what stands for a private part of a URL in an error's text


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
