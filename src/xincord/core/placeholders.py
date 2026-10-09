"""``%key%`` placeholders: single-pass rendering and the v3 key families."""

import functools
from datetime import UTC, datetime
from importlib.resources import files
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

import yaml

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    import discord

# JDA 6.4.1 ChannelType names by Discord channel type number.
CHANNEL_TYPES = {
    0: "TEXT",
    1: "PRIVATE",
    2: "VOICE",
    3: "GROUP",
    4: "CATEGORY",
    5: "NEWS",
    10: "GUILD_NEWS_THREAD",
    11: "GUILD_PUBLIC_THREAD",
    12: "GUILD_PRIVATE_THREAD",
    13: "STAGE",
    14: "GUILD_DIRECTORY",
    15: "FORUM",
    16: "MEDIA",
}
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class AssetLike(Protocol):
    """An image asset, such as :class:`discord.Asset`."""

    @property
    def url(self) -> str:
        """The asset's URL."""
        ...


class UserLike(Protocol):
    """The parts of :class:`discord.User` that placeholders read."""

    @property
    def id(self) -> int:
        """The user ID."""
        ...

    @property
    def name(self) -> str:
        """The unique username."""
        ...

    @property
    def global_name(self) -> str | None:
        """The global display name, if set."""
        ...

    @property
    def mention(self) -> str:
        """The mention markup."""
        ...

    @property
    def avatar(self) -> AssetLike | None:
        """The custom avatar, if set."""
        ...

    @property
    def default_avatar(self) -> AssetLike:
        """The default avatar."""
        ...

    @property
    def bot(self) -> bool:
        """Whether the user is a bot."""
        ...

    @property
    def created_at(self) -> datetime:
        """When the account was created (aware, UTC)."""
        ...


class RoleLike(Protocol):
    """The parts of :class:`discord.Role` that placeholders read."""

    @property
    def name(self) -> str:
        """The role name."""
        ...

    @property
    def mention(self) -> str:
        """The mention markup."""
        ...

    @property
    def position(self) -> int:
        """The position in the role list; higher is more important."""
        ...

    def is_default(self) -> bool:
        """Whether this is the @everyone role."""
        ...


@runtime_checkable
class MemberLike(UserLike, Protocol):
    """The parts of :class:`discord.Member` that placeholders read."""

    @property
    def nick(self) -> str | None:
        """The guild nickname, if set."""
        ...

    @property
    def display_name(self) -> str:
        """The nickname, global name or username, whichever is set first."""
        ...

    @property
    def display_avatar(self) -> AssetLike:
        """The guild avatar, else the user's avatar."""
        ...

    @property
    def roles(self) -> Sequence[RoleLike]:
        """The member's roles, including the default role."""
        ...

    @property
    def joined_at(self) -> datetime | None:
        """When the member joined the guild."""
        ...


class ChannelLike(Protocol):
    """The parts of a discord.py guild channel that placeholders read."""

    @property
    def id(self) -> int:
        """The channel ID."""
        ...

    @property
    def name(self) -> str:
        """The channel name."""
        ...

    @property
    def mention(self) -> str:
        """The mention markup."""
        ...

    @property
    def type(self) -> discord.ChannelType:
        """The channel type."""
        ...


class GuildLike(Protocol):
    """The parts of :class:`discord.Guild` that placeholders read."""

    @property
    def id(self) -> int:
        """The guild ID."""
        ...

    @property
    def name(self) -> str:
        """The guild name."""
        ...

    @property
    def preferred_locale(self) -> discord.Locale:
        """The community's preferred locale."""
        ...

    @property
    def member_count(self) -> int | None:
        """The member count, when known."""
        ...

    @property
    def premium_subscription_count(self) -> int:
        """The number of boosts."""
        ...

    @property
    def icon(self) -> AssetLike | None:
        """The icon, if set."""
        ...

    @property
    def banner(self) -> AssetLike | None:
        """The banner, if set."""
        ...

    @property
    def description(self) -> str | None:
        """The description, if set."""
        ...

    @property
    def owner_id(self) -> int | None:
        """The owner's user ID."""
        ...

    @property
    def owner(self) -> MemberLike | None:
        """The owner, when cached."""
        ...

    @property
    def system_channel(self) -> ChannelLike | None:
        """The system messages channel, if set."""
        ...

    @property
    def rules_channel(self) -> ChannelLike | None:
        """The rules channel, if set."""
        ...


def render(text: str, values: Mapping[str, str]) -> str:
    """Replace each ``%key%`` that has a value, in one left-to-right pass.

    Keys without a value stay as written, ``$%`` is a literal ``%``, and substituted values are
    never scanned again.
    """
    out: list[str] = []
    index = 0
    while (start := text.find("%", index)) != -1:
        if start > index and text[start - 1] == "$":
            out += (text[index : start - 1], "%")
            index = start + 1
            continue
        end = text.find("%", start + 1)
        if end == -1:
            break
        out.append(text[index:start])
        key = text[start + 1 : end]
        if key in values:
            out.append(values[key])
            index = end + 1
        else:
            # The closing % may open the next placeholder, as in commons-text.
            out.append(text[start:end])
            index = end
    out.append(text[index:])
    return "".join(out)


def actor_values(user: UserLike, bot: UserLike) -> dict[str, str]:
    """Return the v3 ``Placeholder.get`` keys for the user acting in an interaction."""
    values = {
        "bot_id": str(bot.id),
        "bot_name": bot.name,
        "user_id": str(user.id),
        "user_mention": user.mention,
        "user_name": user.name,
        "user_avatar_url": (user.avatar or user.default_avatar).url,
    }
    if isinstance(user, MemberLike):
        values |= {
            "member_display_name": user.display_name,
            "member_avatar_url": user.display_avatar.url,
            "member_fixed_name": f"{user.nick} ({user.name})" if user.nick else user.name,
        }
    return values


def user_values(user: UserLike, prefix: str = "", none: str = "-") -> dict[str, str]:
    """Return the v3 ``putUser`` keys, each prefixed with ``prefix``."""
    return _prefixed(
        prefix,
        {
            "user_id": str(user.id),
            "user_name": user.name,
            "user_name_upper": user.name.upper(),
            "user_name_lower": user.name.lower(),
            "user_global_name": _text(user.global_name, none),
            "user_effective_name": user.global_name or user.name,
            "user_mention": user.mention,
            "user_avatar_url": (user.avatar or user.default_avatar).url,
            "user_default_avatar_url": user.default_avatar.url,
            "user_is_bot": "true" if user.bot else "false",
            "user_created_unix": str(_seconds(user.created_at)),
            "user_created_iso": _offset_iso(user.created_at),
        },
    )


def member_values(member: MemberLike, prefix: str = "", none: str = "-") -> dict[str, str]:
    """Return the v3 ``putMember`` keys, each prefixed with ``prefix``."""
    roles = sorted(
        (role for role in member.roles if not role.is_default()),
        key=lambda role: role.position,
        reverse=True,
    )
    joined = member.joined_at
    return _prefixed(
        prefix,
        {
            "member_id": str(member.id),
            "member_display_name": member.display_name,
            "member_nickname": _text(member.nick, none),
            "member_nickname_or_name": member.nick or member.display_name,
            "member_avatar_url": member.display_avatar.url,
            "member_roles_count": str(len(roles)),
            "member_roles_mentions": " ".join(role.mention for role in roles) or none,
            "member_roles_names": ", ".join(role.name for role in roles) or none,
            "member_joined_unix": str(_seconds(joined)) if joined else "0",
            "member_joined_iso": _offset_iso(joined) if joined else none,
        },
    )


def guild_values(guild: GuildLike, prefix: str = "", none: str = "-") -> dict[str, str]:
    """Return the v3 ``putGuild`` keys, each prefixed with ``prefix``."""
    owner, system, rules = guild.owner, guild.system_channel, guild.rules_channel
    boosts = str(guild.premium_subscription_count)
    return _prefixed(
        prefix,
        {
            "guild_id": str(guild.id),
            "guild_name": guild.name,
            "guild_name_upper": guild.name.upper(),
            "guild_name_lower": guild.name.lower(),
            "guild_locale": locale_names(guild.preferred_locale.value)[0],
            "guild_member_count": str(guild.member_count or 0),
            "guild_boost_count": boosts,
            "guild_booster_count": boosts,
            "guild_icon_url": guild.icon.url if guild.icon else none,
            "guild_banner_url": guild.banner.url if guild.banner else none,
            "guild_description": _text(guild.description, none),
            "guild_owner_id": str(guild.owner_id or 0),
            "guild_owner_name": owner.display_name if owner else none,
            "guild_owner_mention": f"<@{guild.owner_id}>" if guild.owner_id else none,
            "guild_system_channel_id": str(system.id) if system else "0",
            "guild_system_channel_name": system.name if system else none,
            "guild_system_channel_mention": system.mention if system else none,
            "guild_rules_channel_id": str(rules.id) if rules else "0",
            "guild_rules_channel_name": rules.name if rules else none,
            "guild_rules_channel_mention": rules.mention if rules else none,
        },
    )


def channel_values(
    channel: ChannelLike | None,
    prefix: str = "",
    base: str = "channel",
    none: str = "-",
) -> dict[str, str]:
    """Return the v3 ``putTextChannel`` keys ``<base>_id``, ``_name``, ``_mention``, ``_type``."""
    if channel is None:
        values = {"id": "0", "name": none, "mention": none, "type": none}
    else:
        values = {
            "id": str(channel.id),
            "name": channel.name,
            "mention": channel.mention,
            "type": CHANNEL_TYPES.get(channel.type.value, "UNKNOWN"),
        }
    return _prefixed(f"{prefix}{base}_", values)


def event_values(event_type: str, prefix: str = "", at: datetime | None = None) -> dict[str, str]:
    """Return the v3 ``putEvent`` keys for an event at ``at`` (default: now)."""
    moment = at or datetime.now(UTC)
    return _prefixed(
        prefix,
        {
            "event_type": event_type,
            "event_timestamp_unix": str(_seconds(moment)),
            "event_timestamp_ms": str((moment - EPOCH) // _MILLISECOND),
            "event_timestamp_iso": _instant_iso(moment),
        },
    )


class MessageLike(Protocol):
    """The parts of :class:`discord.Message` that interaction values read."""

    @property
    def components(self) -> Sequence[object]:
        """The message's top-level components."""
        ...


class InteractionLike(Protocol):
    """The parts of :class:`discord.Interaction` that interaction values read."""

    @property
    def data(self) -> Mapping[str, object] | None:
        """The raw interaction data."""
        ...

    @property
    def locale(self) -> discord.Locale:
        """The user's locale."""
        ...

    @property
    def channel(self) -> object:
        """The channel the interaction came from, if known."""
        ...

    @property
    def message(self) -> MessageLike | None:
        """The message of a component interaction."""
        ...


# Discord option types: subcommand and group nest options; entities resolve to names as in JDA.
SUBCOMMAND_TYPES = (1, 2)
BOOLEAN_OPTION = 5
ENTITY_OPTIONS = {
    6: (("users", "username", "@"),),
    7: (("channels", "name", "#"),),
    8: (("roles", "name", "@"),),
    9: (("roles", "name", "@"), ("users", "username", "@")),
}
CONTEXT_MENU_TYPES = (2, 3)  # user and message commands


def interaction_values(interaction: InteractionLike) -> dict[str, str]:
    """Return v3's interaction keys: ``language``, the channel, and the command or component."""
    data = interaction.data or {}
    values = {"language": locale_names(interaction.locale.value)[1]}
    channel = interaction.channel
    if (name := getattr(channel, "name", None)) is not None:
        values |= {"channel_id": str(getattr(channel, "id", 0)), "channel_name": str(name)}
        if (category := getattr(channel, "category", None)) is not None:
            values["channel_category_name"] = str(getattr(category, "name", ""))
    if "component_type" in data:
        values |= _component_values(str(data.get("custom_id", "")), interaction.message)
    elif "name" in data:
        values |= _command_values(data)
    return values


def _command_values(data: Mapping[str, object]) -> dict[str, str]:
    """The command keys, with ``command_string`` as JDA's ``getCommandString`` built it."""
    name = str(data["name"])
    path, options = [name], _options(data)
    while options and options[0].get("type") in SUBCOMMAND_TYPES:
        path.append(str(options[0].get("name")))
        options = _options(options[0])
    full = " ".join(path)
    values = {"command_name": name, "full_command_name": full}
    if len(path) > 1:
        values["subcommand_name"] = path[-1]
    if data.get("type") in CONTEXT_MENU_TYPES:
        values["command_string"] = name
    else:
        resolved = _mapping(data.get("resolved"))
        text = "".join(
            f" {option.get('name')}: {_option_text(option, resolved)}" for option in options
        )
        values["command_string"] = f"/{full}{text}"
    return values


def _option_text(option: Mapping[str, object], resolved: Mapping[str, object]) -> str:
    kind, value = option.get("type"), option.get("value")
    if kind == BOOLEAN_OPTION:
        return "true" if value else "false"
    for table, field, prefix in ENTITY_OPTIONS.get(cast("int", kind), ()):
        entity = _mapping(_mapping(resolved.get(table)).get(str(value)))
        if field in entity:
            return f"{prefix}{entity[field]}"
    # Unresolved entities (autocomplete) show their raw ID, as in JDA.
    return str(value)


def _component_values(custom_id: str, message: MessageLike | None) -> dict[str, str]:
    values = {"component_id": custom_id}
    component = _find_component(message.components if message else (), custom_id)
    if component is None:
        return values
    if (style := getattr(component, "style", None)) is not None:
        values["component_label"] = getattr(component, "label", None) or ""
        values["component_style"] = str(style.name).upper()
        if (emoji := getattr(component, "emoji", None)) is not None:
            values |= {"component_emoji": str(emoji), "component_emoji_name": str(emoji.name)}
    else:
        values["component_min"] = str(getattr(component, "min_values", 1))
        values["component_max"] = str(getattr(component, "max_values", 1))
        if (placeholder := getattr(component, "placeholder", None)) is not None:
            values["component_placeholder"] = str(placeholder)
    return values


def _find_component(components: Iterable[object], custom_id: str) -> object | None:
    """Search rows, containers and section accessories for the component with ``custom_id``."""
    for component in components:
        if getattr(component, "custom_id", None) == custom_id:
            return component
        nested = [*getattr(component, "children", ()), getattr(component, "accessory", None)]
        if (found := _find_component(filter(None, nested), custom_id)) is not None:
            return found
    return None


def _options(node: Mapping[str, object]) -> list[Mapping[str, object]]:
    options = node.get("options")
    return cast("list[Mapping[str, object]]", options) if isinstance(options, list) else []


def _mapping(value: object) -> Mapping[str, object]:
    return cast("Mapping[str, object]", value) if isinstance(value, dict) else {}


def locale_names(locale: str) -> tuple[str, str]:
    """Return JDA's enum name and native name of a Discord locale such as ``zh-TW``."""
    name, native = _locales().get(locale, ("UNKNOWN", "Unknown"))
    return name, native


_MILLISECOND = EPOCH.resolution * 1000


def _prefixed(prefix: str, values: Mapping[str, str]) -> dict[str, str]:
    return {prefix + key: value for key, value in values.items()}


def _text(value: str | None, none: str) -> str:
    return value if value and value.strip() else none


def _seconds(moment: datetime) -> int:
    return (moment - EPOCH) // (_MILLISECOND * 1000)


def _fraction(moment: datetime) -> str:
    if not moment.microsecond:
        return ""
    digits = f"{moment.microsecond:06d}"
    return "." + (digits[:3] if digits.endswith("000") else digits)


def _offset_iso(moment: datetime) -> str:
    """Format like Java's ``OffsetDateTime.toString()`` in UTC: seconds only when non-zero."""
    moment = moment.astimezone(UTC)
    text = moment.strftime("%Y-%m-%dT%H:%M")
    if moment.second or moment.microsecond:
        text += f":{moment.second:02d}{_fraction(moment)}"
    return f"{text}Z"


def _instant_iso(moment: datetime) -> str:
    """Format like Java's ``Instant.toString()``: seconds always."""
    moment = moment.astimezone(UTC)
    return f"{moment.strftime('%Y-%m-%dT%H:%M:%S')}{_fraction(moment)}Z"


@functools.cache
def _locales() -> dict[str, tuple[str, str]]:
    text = files(__package__).joinpath("resources/locales.yaml").read_text(encoding="utf-8")
    return {code: (names[0], names[1]) for code, names in yaml.safe_load(text).items()}
