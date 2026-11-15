"""The plugin's ``config.yaml``: bulletin's API, the intervals and the boards."""

from typing import TYPE_CHECKING, Annotated

from pydantic import AfterValidator, Field, StringConstraints, field_validator
from yarl import URL

from xincord.core.config import Model

if TYPE_CHECKING:
    from collections.abc import Iterable

API_URL = "https://bulletin.ntust.org/api/v1"
INTERVAL_MAX = 2**63 - 1  # a 64-bit integer
MIN_INTERVAL = 30
MAX_WAIT = 86_400  # a day
SCHEMES = frozenset({"http", "https"})
# A site's ID, or a site's ID and a board's, as bulletin's API names them.
BOARD_KEY = r"^[1-9][0-9]*(-[1-9][0-9]*)?$"
API = "must be an http or https URL with a host, without user info, a query or a fragment"


def _api_url(url: str) -> str:
    """Accept bulletin's API: an http or https URL with a host, without user info, a query, a
    fragment or spaces; a final ``/`` is dropped.

    It is read as aiohttp reads it (yarl), so that every URL that loads can be requested.
    """
    try:
        parsed = URL(url)
    except ValueError:
        raise ValueError(API) from None
    authority = url.partition("://")[2].partition("/")[0]
    if (
        parsed.scheme not in SCHEMES
        or not parsed.host
        or parsed.explicit_port == 0
        or "@" in authority
        or any(character in "?#" or character.isspace() for character in url)
    ):
        raise ValueError(API)
    return url.rstrip("/")


class Board(Model):
    """One board, or every board of a site: its name, key, channel and title prefix."""

    name: Annotated[str, StringConstraints(pattern=r"\S")]  # how the logs name it
    board: Annotated[str, StringConstraints(pattern=BOARD_KEY)]  # `1053-1436`, or `1053`
    # Where its posts go; 0 until it has a channel.
    channel_id: Annotated[int, Field(alias="channel-id", ge=0)]
    # Only the titles that start with it are posted.
    title_prefix: Annotated[str, Field(alias="title-prefix")] = ""

    def matches(self, boards: Iterable[str]) -> bool:
        """Whether one of ``boards``, keys such as `1053-1436`, is this board or on this site."""
        return any(key == self.board or key.startswith(f"{self.board}-") for key in boards)


class Config(Model):
    """``plugins/NtustAnnouncements/config.yaml``, with kebab-case keys.

    The core config's ``plugins`` list enables the plugin; an ``enabled`` key here only warns, as
    do the keys of the scraper that the plugin was. The bundled file sets every channel to 0, so
    the plugin requests nothing until the operator sets one.
    """

    api_url: Annotated[str, Field(alias="api-url"), AfterValidator(_api_url)] = API_URL
    # Seconds between the feed's reads.
    poll_interval: Annotated[
        int, Field(alias="poll-interval", ge=MIN_INTERVAL, le=INTERVAL_MAX)
    ] = 60
    # Seconds a new announcement waits for its rewrite; strict, since YAML reads yes as true.
    rendition_wait: Annotated[
        int, Field(alias="rendition-wait", ge=0, le=MAX_WAIT, strict=True)
    ] = 3600
    boards: tuple[Board, ...]

    @field_validator("boards")
    @classmethod
    def _unique_names(cls, boards: tuple[Board, ...]) -> tuple[Board, ...]:
        """Refuse no boards, and two boards with one name: the logs could not tell them apart."""
        if not boards:
            msg = "list at least one board"
            raise ValueError(msg)
        names: set[str] = set()
        for board in boards:
            if board.name in names:
                msg = f"two boards are named {board.name}"
                raise ValueError(msg)
            names.add(board.name)
        return boards

    @property
    def placeholders(self) -> tuple[Board, ...]:
        """The boards without a channel yet."""
        return tuple(board for board in self.boards if not board.channel_id)
