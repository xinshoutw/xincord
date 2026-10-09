"""Plugin discovery, loading and reloading.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/base/PluginLoader.kt:39-245
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/plugin/PluginEvent.kt:14-74
"""

import importlib
import logging
import sys
import textwrap
import uuid
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint
from typing import TYPE_CHECKING

import discord
import pytest

from xincord.core.plugins import GROUP, PluginInfo, discover, required_intents

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


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

    def calls(self) -> list[str]:
        """The names recorded by the plugins' setup functions so far."""
        record: list[str] = sys.modules[self.package].calls
        return record


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


def test_enabled_plugins_are_discovered(fake_plugins: FakePlugins) -> None:
    """Requirement: Plugins are discovered through entry points."""
    module = fake_plugins.add(
        "Alpha",
        """
        import discord

        SOFT_DEPENDS = ("Gamma",)
        INTENTS = discord.Intents(members=True)
        """,
    )
    fake_plugins.add("Beta")

    infos = discover(["Alpha"], fake_plugins.entry_points)

    assert infos == [
        PluginInfo("Alpha", module, (), ("Gamma",), discord.Intents(members=True)),
    ]


def test_installed_group_is_the_default(caplog: pytest.LogCaptureFixture) -> None:
    """Requirement: Plugins are discovered through entry points."""
    with caplog.at_level(logging.ERROR):
        assert discover(["NotInstalled"]) == []

    assert "NotInstalled" in caplog.text


@pytest.mark.parametrize(
    "source",
    [
        "raise RuntimeError('boom')\n",
        "DEPENDS = 'Alpha'\n",
        "SOFT_DEPENDS = ('Alpha', 1)\n",
        "INTENTS = 3\n",
    ],
)
def test_broken_plugins_are_left_out(
    fake_plugins: FakePlugins, caplog: pytest.LogCaptureFixture, source: str
) -> None:
    """Requirement: Plugins are discovered through entry points."""
    fake_plugins.add("Alpha")
    fake_plugins.add("Broken", source)
    evil = EntryPoint(name="../Evil", value=f"{fake_plugins.package}.alpha", group=GROUP)

    with caplog.at_level(logging.ERROR):
        infos = discover(
            ["Missing", "Alpha", "Broken", "../Evil"], [*fake_plugins.entry_points, evil]
        )

    assert [info.name for info in infos] == ["Alpha"]
    for name in ("Missing", "Broken", "../Evil"):
        assert name in caplog.text


def test_dependencies_first(fake_plugins: FakePlugins) -> None:
    """Requirement: Plugins load in dependency order."""
    fake_plugins.add("Alpha")
    fake_plugins.add("Beta", "SOFT_DEPENDS = ('Alpha',)\n")
    fake_plugins.add("Gamma", "DEPENDS = ('Beta',)\n")

    infos = discover(["Gamma", "Beta", "Alpha"], fake_plugins.entry_points)

    assert [info.name for info in infos] == ["Alpha", "Beta", "Gamma"]


def test_missing_dependencies_and_cycles(
    fake_plugins: FakePlugins, caplog: pytest.LogCaptureFixture
) -> None:
    """Requirement: Plugins load in dependency order."""
    fake_plugins.add("Alpha")
    fake_plugins.add("Delta", "DEPENDS = ('Omega',)\n")
    fake_plugins.add("Epsilon", "DEPENDS = ('Delta',)\n")
    fake_plugins.add("Zeta", "DEPENDS = ('Eta',)\n")
    fake_plugins.add("Eta", "DEPENDS = ('Zeta',)\n")
    fake_plugins.add("Theta", "SOFT_DEPENDS = ('Delta',)\n")

    with caplog.at_level(logging.ERROR):
        infos = discover(
            ["Alpha", "Delta", "Epsilon", "Zeta", "Eta", "Theta"], fake_plugins.entry_points
        )

    assert [info.name for info in infos] == ["Alpha", "Theta"]
    for name in ("Delta", "Epsilon", "Zeta", "Eta"):
        assert name in caplog.text


def test_plugin_intents_are_added(fake_plugins: FakePlugins) -> None:
    """Requirement: Intents are aggregated before connecting."""
    fake_plugins.add("Alpha", "import discord\nINTENTS = discord.Intents(members=True)\n")
    fake_plugins.add("Beta", "import discord\nINTENTS = discord.Intents(message_content=True)\n")
    expected = discord.Intents.default()
    expected.members = True
    expected.message_content = True

    intents = required_intents(discover(["Alpha", "Beta"], fake_plugins.entry_points))

    assert intents == expected
