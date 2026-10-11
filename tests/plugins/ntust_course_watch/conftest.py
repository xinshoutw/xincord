"""Fixtures for the NtustCourseWatch tests: the plugin loads through its real entry point.

READY never comes unless a test sets it, so the plugin's loop waits for it; the loops left running
are cancelled when the test ends. No test reaches the network.
"""

import errno
import sys
from typing import TYPE_CHECKING, Any, cast

import aiohttp
import pytest

from plugin_fakes import Ready, load_plugin

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator
    from pathlib import Path

    from xincord.core.bot import Bot
    from xincord.core.storage import Store
    from xincord.plugins.ntust_course_watch.cog import NtustCourseWatch

PACKAGE = "xincord.plugins.ntust_course_watch"
LOCAL_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


@pytest.fixture(autouse=True)
def plugin_modules() -> Iterator[None]:
    """The plugin's modules, the same before and after each test.

    discord.py drops a plugin's modules when its setup fails (an invalid config), and the next load
    imports new ones, whose classes differ from those that the test modules imported.
    """
    kept = {
        name: module
        for name, module in sys.modules.items()
        if name == PACKAGE or name.startswith(f"{PACKAGE}.")
    }
    yield
    sys.modules.update(kept)


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test reaches the network: aiohttp refuses every host but this machine's.

    The tests' local servers listen on 127.0.0.1; a plugin that a test failed to give its fake API
    would otherwise ask NTUST's real course query.
    """
    resolve = aiohttp.TCPConnector._resolve_host  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]

    async def local_only(
        connector: aiohttp.TCPConnector, host: str, port: int, traces: object = None
    ) -> object:
        if host not in LOCAL_HOSTS:
            msg = f"the tests do not reach the network: {host}"
            raise OSError(errno.EHOSTUNREACH, msg)  # aiohttp's error shows its strerror
        return await resolve(connector, host, port, cast("Any", traces))

    monkeypatch.setattr(aiohttp.TCPConnector, "_resolve_host", local_only)


@pytest.fixture(autouse=True)
async def ready(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[Ready]:
    """READY for the offline bots: the loop waits for it, and the ones left running are stopped."""
    readiness = Ready(monkeypatch)
    yield readiness
    await readiness.close()


@pytest.fixture
def config() -> str | None:
    """The plugin's config.yaml, the bundled one unless a test parametrizes it."""
    return None


@pytest.fixture
async def bot(store: Store, tmp_path: Path, config: str | None) -> Bot:
    """A bot that loaded the plugin with ``config``, offline; its loop waits for READY."""
    return await load_plugin("NtustCourseWatch", tmp_path / "plugins", store, config=config)


@pytest.fixture
def cog(bot: Bot) -> NtustCourseWatch:
    """The loaded plugin's cog."""
    cog = bot.get_cog("NtustCourseWatch")
    assert cog is not None
    return cast("NtustCourseWatch", cog)
