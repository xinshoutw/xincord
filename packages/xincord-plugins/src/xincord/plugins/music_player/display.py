"""What the panels show: the identifier rule, times, progress bar, thumbnails and queue."""

import re
from dataclasses import dataclass
from itertools import accumulate, takewhile
from typing import TYPE_CHECKING

import discord

from xincord.core.placeholders import render

from .audio import STREAM_LENGTH
from .history import LoopMode

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from .audio import Track
    from .history import Entry

PREFIX = "music_player@"  # the placeholder prefix
SEARCH = "ytsearch:"  # a YouTube search for anything that is no link
LINK_HOSTS = ("youtube.com", "youtu.be", "soundcloud.com", "spotify.com")
BAR_LENGTH = 15  # the bar's emojis
STEPS = BAR_LENGTH - 1  # the white segments' positions: 15 bars in all
PLAYING_COLOR = "0x68c06e"
PAUSED_COLOR = "0xba9c55"
QUEUE_COLOR = 0x9BD9D5
YOUTUBE_IMAGE = "https://img.youtube.com/vi/{}/maxresdefault.jpg"
DEFAULT_IMAGE = "https://i.meee.com.tw/GHexAW6.png"  # the fallback thumbnail
# \w is ASCII here: re.ASCII keeps Python's from matching other letters.
YOUTUBE_PATTERNS = tuple(
    re.compile(pattern, re.ASCII)
    for pattern in (
        r"(?:youtube\.com(?:\.\w{2})?/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)",
        r"youtube\.com(?:\.\w{2})?/embed/([a-zA-Z0-9_-]+)",
        r"youtube\.com(?:\.\w{2})?/v/([a-zA-Z0-9_-]+)",
    )
)
QUEUE_FIELD = "\N{EM DASH}"  # the queue fields' name
LINES_PER_FIELD = 10
FIELD_LIMIT = 1024  # Discord's limit for a field's value
MAX_FIELDS = 25  # Discord's limit for an embed's fields
QUEUE_BUDGET = 4000  # of Discord's 6000 for a message's embeds; the track's embed has the rest
TITLE_LIMIT = 200  # a line's title, so that several lines fit a field
AUTHOR_LIMIT = 100
ELLIPSIS = "\N{HORIZONTAL ELLIPSIS}"
BUTTON_EMOJIS = ("media_previous", "media_pause_resume", "media_next", "media_disconnect")


@dataclass(frozen=True)
class Look:
    """What a panel needs besides its song: the emojis by config key and the locale's words."""

    emojis: Mapping[str, str]
    live: str  # text.yaml's `live`, in the bar of a stream
    live_length: str  # text.yaml's `live-length`, a stream's length


def identifier(query: str) -> str:
    """The node's identifier for a member's query.

    Links pass as written (anything that starts with ``http`` or names YouTube, SoundCloud or
    Spotify); everything else is a YouTube search, ``ytsearch:`` prefixes included.
    """
    if query.startswith("http") or any(host in query for host in LINK_HOSTS):
        return query
    return SEARCH + query


def format_time(milliseconds: int) -> str:
    """``mm:ss``, or ``hh:mm:ss`` from an hour on; a negative time reads as ``00:00``."""
    seconds = max(milliseconds, 0) // 1000
    minutes, hours = seconds // 60, seconds // 3600
    if hours:
        return f"{hours:02d}:{minutes % 60:02d}:{seconds % 60:02d}"
    return f"{minutes:02d}:{seconds % 60:02d}"


def _stream(track: Track) -> bool:
    """Whether ``track`` has no length: a stream, whose length is ``STREAM_LENGTH``."""
    return track.stream or track.length == STREAM_LENGTH


def length_text(track: Track, live_length: str) -> str:
    """A song's length: ``live_length`` for a stream."""
    return live_length if _stream(track) else format_time(track.length)


def progress_bar(position: int, track: Track, *, playing: bool, look: Look) -> str:
    """The play or pause emoji, the times and 15 bar emojis.

    A stream, or a song without a length, shows the emoji and ``live`` instead. The bar's step is
    ``floor(position / length * 14)``, kept between 0 and 14.
    """
    emoji = look.emojis["media_play" if playing else "media_pause"]
    if _stream(track) or track.length <= 0:
        return f"{emoji} {look.live}"
    step = min(max(int(position / track.length * STEPS), 0), STEPS)
    return f"{emoji} {format_time(position)}{_bar(step, look.emojis)}{format_time(track.length)}"


def _bar(step: int, emojis: Mapping[str, str]) -> str:
    """The bar at ``step``: the white start, ``step`` white segments and the black rest."""
    start, full = emojis["progress_white_start"], emojis["progress_white_full"]
    if step == STEPS:
        return start + full * (BAR_LENGTH - 2) + emojis["progress_white_end"]
    black = emojis["progress_black"] * (BAR_LENGTH - 2 - step)
    return start + full * step + black + emojis["progress_black_end"]


def youtube_id(url: str) -> str | None:
    """The video ID in a YouTube link, by three patterns, or None."""
    for pattern in YOUTUBE_PATTERNS:
        if match := pattern.search(url):
            return match[1]
    return None


def thumbnail(track: Track) -> str:
    """The node's artwork, YouTube's image of a YouTube link, or the default image.

    For a YouTube link, the video ID comes from the link, else from the song's identifier.
    """
    if track.artwork_url and track.artwork_url.startswith("http"):
        return track.artwork_url
    uri = track.uri or ""
    if "youtube.com" in uri or "youtu.be" in uri:
        return YOUTUBE_IMAGE.format(youtube_id(uri) or track.identifier)
    return DEFAULT_IMAGE


def track_values(
    entry: Entry, *, position: int, playing: bool, loop: LoopMode, look: Look
) -> dict[str, str]:
    """The ``music_player@`` values of a panel showing ``entry``.

    ``playing`` is the player's state (a song playing and not paused), shown for any song a panel
    names; ``position`` is the shown song's, 0 for a song that does not play.
    """
    track, requester = entry.track, entry.requester
    loop_emoji = "media_ordered" if loop is LoopMode.SEQUENTIAL else "media_repeat_once"
    values = {
        "song_author_name": track.author,
        "song_name": track.title,
        "song_url": track.uri or "",
        "song_thumbnail_url": thumbnail(track),
        "track_duration": length_text(track, look.live_length),
        "song_duration": progress_bar(position, track, playing=playing, look=look),
        "song_requester_username": requester.username,
        "song_requester_name": requester.name,
        "song_requester_avatar_url": requester.avatar_url,
        "song_requester_id": str(requester.id),
        "player_current_color": PLAYING_COLOR if playing else PAUSED_COLOR,
        # The key, misspelt, as operators' templates name it.
        "player_currnet_loop_mode_emoji": look.emojis[loop_emoji],
    }
    return {PREFIX + key: value for key, value in values.items()}


def emoji_values(emojis: Mapping[str, str]) -> dict[str, str]:
    """The four button emojis, by their template keys."""
    return {f"{PREFIX}{key}_emoji": emojis[key] for key in BUTTON_EMOJIS}


def queue_embed(entries: Sequence[Entry], *, live_length: str, more: str) -> discord.Embed:
    """The list of the upcoming songs, within Discord's limits; ``more`` counts those left out.

    Each line is ``n. **title** | author `[length]```, ten to a field named with an em dash.
    """
    lines = [_queue_line(number, entry, live_length) for number, entry in enumerate(entries, 1)]
    fields = _pack(lines, QUEUE_BUDGET, MAX_FIELDS)
    if sum(map(len, fields)) < len(lines):
        widest = render(more, {f"{PREFIX}count": str(len(lines))})
        fields = _pack(lines, QUEUE_BUDGET - _units(QUEUE_FIELD + widest), MAX_FIELDS - 1)
        left = len(lines) - sum(map(len, fields))
        fields.append([render(more, {f"{PREFIX}count": str(left)})])
    embed = discord.Embed(colour=QUEUE_COLOR)
    for field in fields:
        embed.add_field(name=QUEUE_FIELD, value="\n".join(field), inline=False)
    return embed


def _queue_line(number: int, entry: Entry, live_length: str) -> str:
    track = entry.track
    title, author = _clip(track.title, TITLE_LIMIT), _clip(track.author, AUTHOR_LIMIT)
    return f"{number}. **{title}** | {author} `[{length_text(track, live_length)}]`"


def _pack(lines: Sequence[str], budget: int, max_fields: int) -> list[list[str]]:
    """The first ``lines`` in fields of ten, within the field limit, ``budget`` and ``max_fields``.

    A line that fits no field ends the list, as one past the budget does.
    """
    fields: list[list[str]] = []
    used = 0
    for line in lines:
        last = fields[-1] if fields else None
        if last is not None and len(last) < LINES_PER_FIELD:
            cost = _units(line) + 1  # and the line break before it
            if _units("\n".join(last)) + cost <= FIELD_LIMIT:
                if used + cost > budget:
                    break
                last.append(line)
                used += cost
                continue
        cost = _units(QUEUE_FIELD) + _units(line)
        if len(fields) == max_fields or used + cost > budget:
            break
        fields.append([line])
        used += cost
    return fields


def _units(text: str) -> int:
    """The length of ``text`` in UTF-16 code units, as Discord counts an embed's characters."""
    return len(text.encode("utf-16-le")) // 2


def cut(text: str, limit: int) -> str:
    """The longest start of ``text`` within ``limit`` UTF-16 code units, whole characters kept."""
    widths = accumulate(_units(char) for char in text)
    return text[: sum(1 for _ in takewhile(lambda width: width <= limit, widths))]


def _clip(text: str, limit: int) -> str:
    """``text`` within ``limit`` UTF-16 code units, cut before a whole character and marked."""
    if _units(text) <= limit:
        return text
    return cut(text, limit - _units(ELLIPSIS)) + ELLIPSIS
