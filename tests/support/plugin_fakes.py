"""Fake plugin packages for tests that load plugins."""

import importlib
import sys
import textwrap
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint
from typing import TYPE_CHECKING

from xincord.core.bot import Bot
from xincord.core.plugins import GROUP, discover

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from xincord.core.storage import Store


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
        record: list[object] = sys.modules[self.package].calls
        return record

    def bot(
        self, enabled: Sequence[str], root: Path, store: Store, *, force_lang: bool = False
    ) -> Bot:
        """Create a bot for the enabled plugins."""
        plugins = discover(enabled, self.entry_points)
        return Bot(plugins, root=root, store=store, force_lang=force_lang)
