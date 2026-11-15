"""The feed's passes: new announcements on the configured boards, posted once per channel."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from xincord.plugins.failures import Failures

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from datetime import datetime

    from .bulletin import Api
    from .config import Board
    from .state import State, States

type Post = Callable[[int, str], Awaitable[int | None]]  # one message to a channel: its ID
type Sleep = Callable[[float], Awaitable[object]]


@dataclass
class Feed:
    """The configured boards and the plugin's effects: the API, the channels and the store."""

    boards: tuple[Board, ...]
    api: Api
    post: Post
    states: States
    wait: float  # seconds an announcement waits for its rewrite
    now: Callable[[], datetime]
    origin: str  # how the logs name the API
    state: State | None = None  # the truth while the plugin runs, once read
    reads: Failures = field(default_factory=Failures)

    async def run(self, interval: float, sleep: Sleep) -> None:
        """Pass at once, then ``interval`` seconds after each pass, until cancelled."""
        while True:
            await self.check()
            await sleep(interval)

    async def check(self) -> None:
        """One pass: read the new events, then post the announcements that are due."""
        raise NotImplementedError
