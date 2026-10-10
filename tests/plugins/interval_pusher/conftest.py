"""Fixtures for the IntervalPusher tests: a local status monitor."""

from typing import TYPE_CHECKING

import pytest

from http_fakes import Monitor, running_monitor

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
async def monitor() -> AsyncGenerator[Monitor]:
    """A status monitor on a free local port, answering 200 unless told otherwise."""
    async with running_monitor() as running:
        yield running
