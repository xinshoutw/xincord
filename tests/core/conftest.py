import sys
import uuid
from typing import TYPE_CHECKING

import pytest

from plugin_fakes import FakePlugins
from xincord.core.storage import Store

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator
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
