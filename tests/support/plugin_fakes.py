"""Fakes for tests that load plugins and run the bot."""

import asyncio
import importlib
import textwrap
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import yaml

from xincord.core.bot import Bot
from xincord.core.plugins import GROUP, discover
from xincord.core.storage import Store

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    import pytest

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
        self, enabled: Sequence[str], root: Path, store: Store, *, force_lang: bool = False
    ) -> Bot:
        """Create a bot for the enabled plugins."""
        plugins = discover(enabled, self.entry_points)
        return Bot(plugins, root=root, store=store, force_lang=force_lang)


FIXTURES = Path(__file__).parent.parent / "fixtures"


def golden(package: str) -> dict[str, Any]:
    """Load ``tests/fixtures/plugins/<package>/golden.yaml``, a plugin's expected output."""
    path = FIXTURES / "plugins" / package / "golden.yaml"
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data


async def load_plugin(name: str, root: Path, store: Store, *, config: str | None = None) -> Bot:
    """Load the installed plugin ``name`` through its entry point, as startup does, offline.

    ``setup_hook`` sets the command translator and runs the plugin's ``setup``; ``root`` takes
    the place of ``plugins/``. ``config``, when given, is written to ``<root>/<name>/config.yaml``
    first, as an operator's file.
    """
    if config is not None:
        path = root / name / "config.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(config, encoding="utf-8")
    bot = Bot(discover([name]), root=root, store=store)
    await bot.setup_hook()
    return bot


WAIT = 5  # seconds before until() gives up


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
