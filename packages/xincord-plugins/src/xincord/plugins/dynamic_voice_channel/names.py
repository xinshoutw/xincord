"""The names of the rooms, from the binding's format 1."""

from typing import TYPE_CHECKING

from xincord.core.placeholders import actor_values, render

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xincord.core.placeholders import MemberLike, UserLike

SEPARATOR = " - "  # %dvc@custom_name% is the display name up to the first one
NAME_MAX = 100  # Discord's longest channel name, which JDA counted in UTF-16 code units


def custom_name(display_name: str) -> str:
    """v3's ``%dvc@custom_name%``: the display name up to its first `` - ``.

    discord.py's ``display_name`` is the nickname, else the global name, else the username, as
    JDA's ``effectiveName``.
    """
    return display_name.split(SEPARATOR, 1)[0]


def room_values(member: MemberLike, bot: UserLike) -> dict[str, str]:
    """The values of format 1: v3's ``Placeholder.get(member)`` and ``dvc@custom_name``."""
    return actor_values(member, bot) | {"dvc@custom_name": custom_name(member.display_name)}


def room_name(template: str, values: Mapping[str, str]) -> str | None:
    """Render ``template`` into a channel name, or None if it is blank or too long.

    The rendering is a single pass, so names typed by members stay as written; v3 expanded them
    again. JDA's ``setName`` refused a blank name and one over 100 UTF-16 code units after trimming
    it, which skipped the rest of v3's request.
    """
    name = render(template, values).strip()
    if not name or len(name.encode("utf-16-le")) // 2 > NAME_MAX:
        return None
    return name
