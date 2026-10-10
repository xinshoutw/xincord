"""Fakes for tests that load plugins and run the bot."""

import asyncio
import gc
import importlib
import textwrap
import warnings
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import patch

import yaml

from xincord.core.bot import Bot
from xincord.core.plugins import GROUP, discover
from xincord.core.storage import Store

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    import discord
    import pytest
    from discord.state import ConnectionState
    from discord.types.guild import Guild as GuildPayload

    from xincord.core.command_tree import CommandTree


@dataclass
class FakePlugins:
    """Writes plugin packages into a directory on ``sys.path``.

    The package's ``calls`` list survives reloads, so plugins can record their setup calls.
    """

    root: Path
    package: str
    entry_points: list[EntryPoint] = field(default_factory=list[EntryPoint])

    def add(self, name: str, source: str = "", files: dict[str, str] | None = None) -> str:
        """Write plugin ``name`` and register its entry point; return its module name."""
        module = f"{self.package}.{name.lower()}"
        directory = self.root / self.package / name.lower()
        directory.mkdir(parents=True)
        (directory / "__init__.py").write_text(textwrap.dedent(source), encoding="utf-8")
        for relative, text in (files or {}).items():
            path = directory / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(text), encoding="utf-8")
        self.entry_points.append(EntryPoint(name=name, value=module, group=GROUP))
        importlib.invalidate_caches()
        return module

    def replace(self, name: str, source: str) -> None:
        """Rewrite the source of plugin ``name``, as a code update on disk would."""
        path = self.root / self.package / name.lower() / "__init__.py"
        path.write_text(textwrap.dedent(source), encoding="utf-8")

    def calls(self) -> list[object]:
        """What the plugins' setup functions recorded so far."""
        record: list[object] = importlib.import_module(self.package).calls
        return record

    def bot(
        self,
        enabled: Sequence[str],
        root: Path,
        store: Store,
        *,
        force_lang: bool = False,
        data: Path | None = None,
    ) -> Bot:
        """Create a bot for the enabled plugins.

        Their data directories are under ``data``, by default ``data`` beside the packages' root,
        inside the test's temporary directory.
        """
        plugins = discover(enabled, self.entry_points)
        data = self.root.parent / "data" if data is None else data
        return Bot(plugins, root=root, data=data, store=store, force_lang=force_lang)


FIXTURES = Path(__file__).parent.parent / "fixtures"


def golden(package: str) -> dict[str, Any]:
    """Load ``tests/fixtures/plugins/<package>/golden.yaml``, a plugin's expected output."""
    path = FIXTURES / "plugins" / package / "golden.yaml"
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


async def load_plugin(name: str, root: Path, store: Store, *, config: str | None = None) -> Bot:
    """Load the installed plugin ``name`` through its entry point, as startup does, offline.

    ``setup_hook`` sets the command translator and runs the plugin's ``setup``; ``root`` takes
    the place of ``plugins/``, and ``data`` beside it the place of ``data/``. ``config``, when
    given, is written to ``<root>/<name>/config.yaml`` first, as an operator's file.
    """
    if config is not None:
        path = root / name / "config.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(config, encoding="utf-8")
    bot = Bot(discover([name]), root=root, data=root.parent / "data", store=store)
    await bot.setup_hook()
    return bot


async def dispatch(bot: Bot, event: str, *args: object) -> None:
    """Run the listeners that the loaded plugins added for ``event``, one after the other.

    ``bot.dispatch`` schedules the same listeners as tasks, but it needs the event loop of a bot
    that logged in.
    """
    for listener in bot.extra_events.get(f"on_{event}", []):
        await listener(*args)


def parsers(bot: Bot) -> dict[str, Callable[[Any], None]]:
    """discord.py's table of gateway event parsers, which its gateway calls with each payload.

    Every connection of the client looks events up in this same dictionary.
    """
    return bot._connection.parsers  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]


async def gateway(bot: Bot, event: str, payload: dict[str, object]) -> None:
    """Hand ``payload`` to the bot's parser of ``event``, as discord.py's gateway does.

    The events that the parser dispatches, through ``bot.dispatch`` (relayed events) or through
    the connection state's ``dispatch`` (discord.py's own parsers), are recorded instead of
    scheduled, then their listeners run one after the other, as :func:`dispatch` runs them.
    """
    dispatched: list[tuple[str, tuple[object, ...]]] = []

    def record(name: str, *args: object) -> None:
        dispatched.append((name, args))

    with patch.object(bot, "dispatch", record), patch.object(_state(bot), "dispatch", record):
        parsers(bot)[event](payload)
    for name, args in dispatched:
        await dispatch(bot, name, *args)


async def burst(bot: Bot, events: Sequence[tuple[str, dict[str, object]]]) -> None:
    """Parse ``events`` before any listener runs, then run the listeners as concurrent tasks.

    discord.py parses the gateway frames that arrived together one after the other without
    yielding, and runs each listener it dispatched as a task, in dispatch order: a listener can
    find its objects changed by later events, and its awaits interleave with the other tasks'.
    """
    dispatched: list[tuple[str, tuple[object, ...]]] = []

    def record(name: str, *args: object) -> None:
        dispatched.append((name, args))

    with patch.object(bot, "dispatch", record), patch.object(_state(bot), "dispatch", record):
        for event, payload in events:
            parsers(bot)[event](payload)
    await asyncio.gather(
        *(
            listener(*args)
            for name, args in dispatched
            for listener in bot.extra_events.get(f"on_{name}", [])
        )
    )


def add_guild(bot: Bot, payload: dict[str, object]) -> discord.Guild:
    """Cache the guild of ``payload`` (``payloads.guild``) as its ``GUILD_CREATE`` would.

    Its channels and threads join discord.py's cache, so that the messages that
    :func:`gateway` parses get them.
    """
    data = cast("GuildPayload", payload)
    return _state(bot)._add_guild_from_data(data)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]


def _state(bot: Bot) -> ConnectionState[Bot]:
    """discord.py's connection state, which caches guilds and parses gateway events."""
    return bot._connection  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]


WAIT = 5  # seconds before until() gives up


def unclosed() -> list[str]:
    """Collect the garbage and return the warnings about resources that nothing closed.

    Python warns when it collects an unclosed ``sqlite3`` connection; recorded here, the warning
    fails the test that leaked it instead of whichever test runs when the collector does.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        gc.collect()
    return [str(warning.message) for warning in caught if warning.category is ResourceWarning]


def write_config(text: str) -> None:
    """Write the core ``config.yaml`` in the working directory."""
    Path("config.yaml").write_text(text, encoding="utf-8")


async def until(condition: Callable[[], bool]) -> None:
    """Wait until ``condition`` holds, for example after a signal handler started a task.

    Raises:
        TimeoutError: It did not hold within ``WAIT`` seconds.
    """
    async with asyncio.timeout(WAIT):
        while not condition():  # noqa: ASYNC110 - the state has no event to wait on
            await asyncio.sleep(0.01)


class Ready:
    """Stands for the gateway's READY in bots that never log in.

    While it exists, ``Bot.wait_until_ready`` waits until :meth:`set` is called (discord.py's
    raises before a login); :meth:`close` cancels the tasks that waited and still run, such as a
    plugin's background loops.
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._event = asyncio.Event()
        self._waited = asyncio.Condition()
        self.tasks: list[asyncio.Task[Any]] = []

        async def wait_until_ready(_bot: Bot) -> None:
            async with self._waited:
                if (task := asyncio.current_task()) is not None:
                    self.tasks.append(task)
                self._waited.notify_all()
            await self._event.wait()

        monkeypatch.setattr(Bot, "wait_until_ready", wait_until_ready)

    def set(self) -> None:
        """The bot is ready: every waiter goes on, and later ones do not wait."""
        self._event.set()

    async def waiters(self, count: int) -> None:
        """Wait until ``count`` tasks have waited for READY.

        Raises:
            TimeoutError: They did not within ``WAIT`` seconds.
        """
        async with asyncio.timeout(WAIT), self._waited:
            await self._waited.wait_for(lambda: len(self.tasks) >= count)

    async def close(self) -> None:
        """Cancel the tasks that waited for READY and are still running, and wait for them."""
        running = [task for task in self.tasks if not task.done()]
        for task in running:
            task.cancel()
        await asyncio.gather(*running, return_exceptions=True)


def watch_syncs(
    bot: Bot, store: Store, monkeypatch: pytest.MonkeyPatch
) -> list[tuple[str | int, bool]]:
    """Record the bot's command uploads as ``(scope, force)`` instead of sending them."""
    syncs: list[tuple[str | int, bool]] = []
    tree = cast("CommandTree", bot.tree)

    async def sync_global(used: Store, *, force: bool = False) -> bool:
        assert used is store
        syncs.append(("global", force))
        return True

    async def sync_guild(used: Store, guild_id: int, *, force: bool = False) -> bool:
        assert used is store
        syncs.append((guild_id, force))
        return True

    monkeypatch.setattr(tree, "sync_global", sync_global)
    monkeypatch.setattr(tree, "sync_guild", sync_guild)
    return syncs


def watch_closes(monkeypatch: pytest.MonkeyPatch) -> list[Store]:
    """Record the stores that are closed."""
    closed: list[Store] = []
    close = Store.close

    async def recording(self: Store) -> None:
        closed.append(self)
        await close(self)

    monkeypatch.setattr(Store, "close", recording)
    return closed
