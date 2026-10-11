"""The Example config."""

import logging
from typing import TYPE_CHECKING

from plugin_fakes import load_plugin
from xincord.plugins.example.cog import Example

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from xincord.core.storage import Store

ENABLED_CONFIG = 'enabled: false\nexample_key: "from-file"\n'


async def load_with(config: str, tmp_path: Path, store: Store) -> Example:
    """Write `config` as the plugin's config.yaml, then load the plugin."""
    path = tmp_path / "plugins" / "Example" / "config.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(config, encoding="utf-8")
    bot = await load_plugin("Example", tmp_path / "plugins", store)
    cog = bot.get_cog("Example")
    assert isinstance(cog, Example)
    return cog


async def test_missing_key_uses_the_default(tmp_path: Path, store: Store) -> None:
    """Requirement: The config holds an example key."""
    cog = await load_with("", tmp_path, store)

    assert cog.config.example_key == "example_value"


async def test_config_with_enabled_key(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config holds an example key."""
    with caplog.at_level(logging.WARNING):
        cog = await load_with(ENABLED_CONFIG, tmp_path, store)

    assert cog.config.example_key == "from-file"
    assert "unknown key enabled" in caplog.text
    assert "unknown key example_key" not in caplog.text
