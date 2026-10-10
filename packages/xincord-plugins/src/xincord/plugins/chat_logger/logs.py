"""What a log shows of a message's channel and author.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/ChatLogger.kt:132-226
    XsDiscordBotKt@3a59607:Plugins/ChatLogger/src/main/kotlin/logger/chat/ChannelData.kt:31-46
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from xincord.core.placeholders import actor_values

if TYPE_CHECKING:
    from xincord.core.placeholders import UserLike
    from xincord.plugins.listen_channels.settings import ChannelIds

NONE = "-"  # stands for a missing category or name, as the core's values do for missing names
# v3's member keys for an author who is no member, such as a webhook: the names show "-" and the
# avatar URL is empty, so the templates' thumbnails are left out.
NO_MEMBER = {"member_display_name": NONE, "member_avatar_url": "", "member_fixed_name": NONE}


@dataclass(frozen=True)
class Place:
    """A message's channel, as the settings detect it and the logs show it.

    It is read from discord.py's cache when the event arrives, before anything awaits: later
    events change the cache meanwhile.
    """

    id: int
    parent_id: int | None = None  # a thread's channel
    category_id: int | None = None  # the channel's category, or the category of a thread's channel

    @classmethod
    def of(cls, channel_id: int, channel: object | None) -> Self:
        """The place of channel ``channel_id``, from its cached ``channel`` (None if uncached).

        A thread's category is its channel's; discord.py's ``Thread.category_id`` raises when
        the channel is not cached, so the channel is looked up instead.
        """
        parent_id = _id(getattr(channel, "parent_id", None))
        if parent_id is None:
            return cls(channel_id, None, _id(getattr(channel, "category_id", None)))
        parent = getattr(channel, "parent", None)  # None when discord.py has not cached it
        return cls(channel_id, parent_id, _id(getattr(parent, "category_id", None)))

    @property
    def ids(self) -> ChannelIds:
        """The channel's ID and the IDs that hold it, for the settings' detection."""
        return (self.id, self.parent_id, self.category_id)

    def values(self) -> dict[str, str]:
        """v3's ``cl_channel_mention`` and ``cl_category_mention``, ``-`` without a category.

        v3 set the category only when the channel had one, so other channels showed an earlier
        event's category or the placeholder.
        """
        category = NONE if self.category_id is None else f"<#{self.category_id}>"
        return {"cl_channel_mention": f"<#{self.id}>", "cl_category_mention": category}


def _id(value: object) -> int | None:
    """``value`` if it is an ID, else None."""
    return value if isinstance(value, int) else None


def author_values(author: UserLike, bot: UserLike) -> dict[str, str]:
    """v3's ``Placeholder.get(member)`` for a message's author, with the bot's keys.

    A webhook, or a user who is no member, has no member keys: ``-`` and no avatar. v3 rendered a
    webhook's edit with the global substitutor, which left every user key as written.
    """
    return NO_MEMBER | actor_values(author, bot)


def unknown_author(user_id: int) -> dict[str, str]:
    """The user and member keys of a stored author whom Discord no longer knows as a member.

    The mention of the stored ID still names them, a webhook too; the names show ``-`` and there
    is no avatar, so the templates show no thumbnail. v3 posted nothing then.
    """
    return NO_MEMBER | {
        "user_id": str(user_id),
        "user_mention": f"<@{user_id}>",
        "user_name": NONE,
        "user_avatar_url": "",
    }


def message_url(guild_id: int, channel_id: int, message_id: int) -> str:
    """A message's link, as JDA's ``jumpUrl`` and discord.py's ``jump_url`` build it."""
    return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
