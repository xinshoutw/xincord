"""The Example config.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/_Example/src/main/kotlin/_example/config/ConfigSerializer.kt:6-12
    XsDiscordBotKt@3a59607:Plugins/_Example/src/main/resources/config.yaml:1-2
"""

import logging
from typing import TYPE_CHECKING

from plugin_fakes import load_plugin
from xincord.plugins.example.cog import Example

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from xincord.core.storage import Store

V3_CONFIG = 'enabled: false\nexample_key: "from-v3"\n'


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


async def test_v3_config_file(
    tmp_path: Path, store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: The config holds an example key."""
    with caplog.at_level(logging.WARNING):
        cog = await load_with(V3_CONFIG, tmp_path, store)

    assert cog.config.example_key == "from-v3"
    assert "unknown key enabled" in caplog.text
    assert "unknown key example_key" not in caplog.text
