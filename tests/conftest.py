"""Fixtures shared by the core and the plugin tests."""

from typing import TYPE_CHECKING

import pytest

from xincord.core.storage import Store

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture(autouse=True)
def no_token_from_the_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a developer's XINCORD_TOKEN out of the tests; a test sets its own."""
    monkeypatch.delenv("XINCORD_TOKEN", raising=False)


@pytest.fixture
async def store() -> AsyncGenerator[Store]:
    opened = await Store.open(":memory:")
    yield opened
    await opened.close()
