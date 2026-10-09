import sys
import uuid
from importlib import metadata
from typing import TYPE_CHECKING

import pytest

from plugin_fakes import FakePlugins
from xincord.core.plugins import GROUP
from xincord.core.storage import Store

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator
    from importlib.metadata import EntryPoint
    from pathlib import Path


@pytest.fixture
async def store() -> AsyncGenerator[Store]:
    opened = await Store.open(":memory:")
    yield opened
    await opened.close()


@pytest.fixture
def fake_plugins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[FakePlugins]:
    package = f"fake_plugins_{uuid.uuid4().hex[:8]}"
    root = tmp_path / "site"
    (root / package).mkdir(parents=True)
    (root / package / "__init__.py").write_text("calls = []\n", encoding="utf-8")
    monkeypatch.setattr(sys, "path", [str(root), *sys.path])
    yield FakePlugins(root, package)
    for name in [name for name in sys.modules if name.split(".")[0] == package]:
        del sys.modules[name]


@pytest.fixture
def installed(
    fake_plugins: FakePlugins, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> FakePlugins:
    """Make the fake plugins the installed ones and work in an empty directory."""

    def entry_points(*, group: str) -> list[EntryPoint]:
        assert group == GROUP
        return fake_plugins.entry_points

    monkeypatch.setattr(metadata, "entry_points", entry_points)
    workdir = tmp_path / "bot"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    return fake_plugins
