"""Rendering Components V2 templates into discord.py layout items."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    import discord

    from xincord.core.templates.base import IdBuilder, Item
    from xincord.core.templates.schema_v2 import ActionRowV2, TopLevelV2


def layout_view(
    components: Sequence[TopLevelV2],
    rows: Sequence[list[Item]],
    values: Mapping[str, str],
    build_id: IdBuilder | None,
    models: Mapping[str, object] | None,
) -> tuple[discord.ui.LayoutView, tuple[discord.File, ...]]:
    """Build a stopped layout view and the files it references.

    ``rows`` are the rendered v1 rows, used as action rows when ``components`` is empty.
    """
    raise NotImplementedError


def row_items(
    row: ActionRowV2,
    values: Mapping[str, str],
    build_id: IdBuilder | None,
    models: Mapping[str, object] | None,
) -> list[Item]:
    """Render the buttons and selects of a V2 action row for a message without V2 mode."""
    raise NotImplementedError
