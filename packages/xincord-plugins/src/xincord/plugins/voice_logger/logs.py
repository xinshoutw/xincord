"""What a log shows of a voice channel, and the template and values of a voice change."""

from dataclasses import dataclass
from typing import Protocol, Self

NONE = "-"  # stands for a missing category or member, as the core's values do for missing names
# v3's member keys when no member is known: texts show "-", and the avatar URLs are empty, so the
# templates' thumbnails are left out.
UNKNOWN_MEMBER = {
    "user_id": "0",
    "user_mention": NONE,
    "user_name": NONE,
    "user_avatar_url": "",
    "member_display_name": NONE,
    "member_avatar_url": "",
    "member_fixed_name": NONE,
}


class VoiceChannelLike(Protocol):
    """A voice or stage channel, as the logs show it."""

    @property
    def id(self) -> int:
        """The channel ID."""
        ...

    @property
    def name(self) -> str:
        """The channel's name."""
        ...

    @property
    def mention(self) -> str:
        """The channel's mention, ``<#id>``."""
        ...

    @property
    def jump_url(self) -> str:
        """The channel's URL, as JDA's ``jumpUrl``."""
        ...

    @property
    def category_id(self) -> int | None:
        """The ID of the channel's category, if it has one."""
        ...


@dataclass(frozen=True)
class Place:
    """A voice channel as a log shows it, read when the event arrived."""

    id: int
    name: str
    mention: str
    url: str
    category_id: int | None

    @classmethod
    def of(cls, channel: VoiceChannelLike) -> Self:
        """What the logs show of ``channel`` now."""
        return cls(channel.id, channel.name, channel.mention, channel.jump_url, channel.category_id)

    @property
    def category_mention(self) -> str:
        """The category's mention, or ``-`` outside categories (v3 left the key unset)."""
        return NONE if self.category_id is None else f"<#{self.category_id}>"


def voice_change(joined: Place | None, left: Place | None) -> tuple[str, dict[str, str]] | None:
    """The template and the values of a voice change, or None when the channel stays.

    discord.py also reports mutes, deafens and streams, which keep the channel; JDA's voice update
    did not. A switch has both sides' values: v3 never set the joined channel's mention there.
    """
    if joined is None:
        return None if left is None else ("on-channel-left", _side(left, "left"))
    if left is None:
        return "on-channel-join", _side(joined, "join")
    if joined.id == left.id:
        return None
    return "on-channel-switch", _side(joined, "join") | _side(left, "left")


def _side(place: Place, side: str) -> dict[str, str]:
    """v3's ``vl_channel_<side>_*`` and ``vl_category_<side>_mention`` values of ``place``."""
    return {
        f"vl_channel_{side}_mention": place.mention,
        f"vl_channel_{side}_name": place.name,
        f"vl_channel_{side}_url": place.url,
        f"vl_category_{side}_mention": place.category_mention,
    }
