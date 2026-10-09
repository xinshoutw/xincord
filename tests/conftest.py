"""Fixtures shared by the core and the plugin tests."""

from typing import TYPE_CHECKING

import pytest

from xincord.core.storage import Store

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
async def store() -> AsyncGenerator[Store]:
    opened = await Store.open(":memory:")
    yield opened
    await opened.close()
