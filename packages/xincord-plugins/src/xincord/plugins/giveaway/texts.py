"""The texts that v3 wrote in its code, in one language per message, and the embeds built from them.

Kotlin:
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/Giveaway.kt:621-627
    XsDiscordBotKt@3a59607:Plugins/Giveaway/src/main/kotlin/giveaway/create/StepManager.kt:313-371
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord

from xincord.core.placeholders import render

from .inputs import clip, thumbnail, trim
from .model import Policy
from .times import format_end_time

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import tzinfo

    from xincord.core.i18n import Lang
    from xincord.core.templates import IdBuilder

    from .model import Draft, Instance, Prize

CHINESE = "zh-TW"  # v3's zh texts
ENGLISH = "en-US"  # v3's other texts
TEXT = "text"  # the stem of the lang file that holds them

PREVIEW_COLOR = 0x2ECC71  # v3's green
# Discord's limits, which JDA's EmbedBuilder checked.
TITLE_MAX = 256
FIELD_NAME_MAX = 256
FIELD_VALUE_MAX = 1024
# JDA's EmbedBuilder.ZERO_WIDTH_SPACE (a left-to-right mark) for an empty field, which Discord
# refuses.
EMPTY_FIELD = chr(0x200E)


def language(lang: Lang, locale: str) -> str:
    """The locale whose texts and templates serve a user or a giveaway of ``locale``.

    The plugin's own files for the locale when it has them; else, as v3's hard-coded texts chose,
    zh-TW for a ``zh`` locale and en-US for any other. v3 took the templates from the configured
    default locale instead, so one message could mix two languages.
    """
    if locale in lang.locales:
        return locale
    return CHINESE if locale.partition("-")[0].lower() == "zh" else ENGLISH


@dataclass(frozen=True)
class Texts:
    """The texts of ``text.yaml`` in one locale, each falling back to the default locale."""

    lang: Lang
    locale: str

    def get(self, key: str, values: Mapping[str, str] | None = None) -> str:
        """The text ``key`` of ``text.yaml`` with its ``%ga@...%`` values, inserted as written."""
        return render(self.lang.text(f"{TEXT}.{key}", self.locale), values or {})


def preview(draft: Draft, texts: Texts, zone: tzinfo | None) -> discord.Embed:
    """The builder's preview of ``draft``, v3's ``ga@preview-embed``.

    v3's green embed: the title, or v3's draft title while it is blank; the description, the end
    time (Discord's full date and the time in ``zone``), the prizes, the winner policy, the total
    winner slots and the sponsor, unset ones ``Not set``; the thumbnail; v3's footer. Values are
    inserted as written. The description and the prize list are clipped to 1024 characters, where
    v3's preview failed and the builder stopped updating.
    """
    not_set = texts.get("preview.not-set")
    title = (
        texts.get("preview.title", {"ga@title": draft.title})
        if trim(draft.title)
        else texts.get("preview.draft")
    )
    end_time = (
        f"<t:{draft.end_at}:F>\n{format_end_time(draft.end_at, zone)}"
        if draft.end_at > 0
        else not_set
    )
    prizes = prize_lines(draft.prizes, texts) if draft.prizes else texts.get("preview.no-prizes")
    policy = (
        "preview.unique"
        if draft.policy is Policy.UNIQUE_ACROSS_PRIZES
        else "preview.allow-duplicate"
    )
    slots = sum(max(prize.winner_count, 1) for prize in draft.prizes)

    embed = discord.Embed(title=clip(title, TITLE_MAX), colour=PREVIEW_COLOR)
    add_field(embed, texts.get("preview.description"), _or(draft.description, not_set))
    add_field(embed, texts.get("preview.end-time"), end_time)
    add_field(embed, texts.get("preview.prizes"), prizes)
    add_field(embed, texts.get("preview.policy"), texts.get(policy))
    add_field(embed, texts.get("preview.slots"), str(slots), inline=True)
    add_field(embed, texts.get("preview.sponsor"), _or(draft.sponsor, not_set), inline=True)
    if (url := thumbnail(draft.thumbnail_url)) is not None:
        embed.set_thumbnail(url=url)
    embed.set_footer(text=texts.get("preview.footer"))
    return embed


def prize_lines(prizes: Sequence[Prize], texts: Texts) -> str:
    """One ``N. name (count winner(s))`` line per prize, as v3's preview and post wrote them."""
    return "\n".join(
        texts.get(
            "prize",
            {
                "ga@index": str(index),
                "ga@prize-name": prize.name,
                "ga@winner-count": str(prize.winner_count),
            },
        )
        for index, prize in enumerate(prizes, start=1)
    )


def add_field(embed: discord.Embed, name: str, value: str, *, inline: bool = False) -> None:
    """Add a field within Discord's limits, as JDA's ``addField`` with v3's clipping."""
    embed.add_field(
        name=clip(name, FIELD_NAME_MAX) or EMPTY_FIELD,
        value=clip(value, FIELD_VALUE_MAX) or EMPTY_FIELD,
        inline=inline,
    )


def _or(value: str, default: str) -> str:
    """``value``, or ``default`` while it is blank, as Kotlin's ``ifBlank``."""
    return value if trim(value) else default


def post_embed(instance: Instance, texts: Texts, now: int) -> discord.Embed:
    """The giveaway's post, v3's ``ga@giveaway-embed``."""
    raise NotImplementedError


def post_buttons(
    instance: Instance, texts: Texts, now: int, build_id: IdBuilder
) -> tuple[discord.ui.Button[discord.ui.View], ...]:
    """The post's join, draw and reroll buttons, v3's three ``ga@*-button`` models."""
    raise NotImplementedError
