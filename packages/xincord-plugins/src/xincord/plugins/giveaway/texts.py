"""The plugin's texts, in one language per message, and the embeds built from them."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord

from xincord.core.placeholders import render

from .inputs import MORE, clip, thumbnail, trim, units
from .model import Policy
from .times import format_end_time

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import tzinfo

    from xincord.core.i18n import Lang
    from xincord.core.templates import IdBuilder

    from .model import Draft, Instance, Prize

CHINESE = "zh-TW"  # for a zh locale
ENGLISH = "en-US"  # for any other
TEXT = "text"  # the stem of the lang file that holds them

PREVIEW_COLOR = 0x2ECC71  # green
RUNNING_COLOR = 0xF1C40F  # gold, while a giveaway runs
DRAWN_COLOR = 0x95A5A6  # gray, once drawn
# Discord's limits of an embed.
TITLE_MAX = 256
FIELD_NAME_MAX = 256
FIELD_VALUE_MAX = 1024
DESCRIPTION_MAX = 4096
EMBED_MAX = 6000  # the total of an embed's texts
RESULT_MAX = 1800  # the bound of a draw result's body
# A left-to-right mark for an empty field, which Discord refuses.
EMPTY_FIELD = chr(0x200E)


def language(lang: Lang, locale: str) -> str:
    """The locale whose texts and templates serve a user or a giveaway of ``locale``.

    The plugin's own files for the locale when it has them; else zh-TW for a ``zh`` locale and
    en-US for any other, for the texts and the templates alike.
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
    """The builder's preview of ``draft``, ``ga@preview-embed``.

    A green embed: the title, or the draft title while it is blank; the description, the end
    time (Discord's full date and the time in ``zone``), the prizes, the winner policy, the total
    winner slots and the sponsor, unset ones ``Not set``; the thumbnail; the footer. Values are
    inserted as written. The description and the prize list are clipped to 1024 characters.
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
    """One ``N. name (count winner(s))`` line per prize, for the preview and the post."""
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
    """Add a field within Discord's limits, its name and value clipped."""
    embed.add_field(
        name=clip(name, FIELD_NAME_MAX) or EMPTY_FIELD,
        value=clip(value, FIELD_VALUE_MAX) or EMPTY_FIELD,
        inline=inline,
    )


def _or(value: str, default: str) -> str:
    """``value``, or ``default`` while it is blank."""
    return value if trim(value) else default


def post_embed(instance: Instance, texts: Texts, now: int) -> discord.Embed:
    """The giveaway's post, ``ga@giveaway-embed``.

    An embed, gold while running and gray once drawn: the title as written, the description or
    the default, the status at ``now`` with the end time, the participants, the winner policy,
    the prizes, the winners (or not drawn yet), the sponsor when set, the thumbnail and the ID.
    Fields are clipped to 1024 characters, and the description so that the embed holds
    at most 6000, which Discord refuses beyond.
    """
    config = instance.config
    end = config.end_at
    if instance.ended:
        status = texts.get("post.drawn")
    else:
        status = texts.get("post.ready") if now >= end else texts.get("post.running")
    unique = config.policy is Policy.UNIQUE_ACROSS_PRIZES
    results = winner_lines(instance, texts) if instance.ended else texts.get("post.not-drawn")
    embed = discord.Embed(
        title=clip(texts.get("post.title", {"ga@title": config.title}), TITLE_MAX),
        description=clip(_or(config.description, texts.get("post.description")), DESCRIPTION_MAX),
        colour=DRAWN_COLOR if instance.ended else RUNNING_COLOR,
    )
    add_field(embed, texts.get("post.status"), f"{status}\n<t:{end}:R>", inline=True)
    add_field(
        embed, texts.get("post.participants"), str(len(instance.participant_ids)), inline=True
    )
    add_field(
        embed,
        texts.get("post.policy"),
        texts.get("post.unique" if unique else "post.allow-duplicate"),
    )
    add_field(embed, texts.get("post.prizes"), prize_lines(config.prizes, texts))
    add_field(embed, texts.get("post.results"), results)
    if trim(config.sponsor):
        add_field(embed, texts.get("post.sponsor"), config.sponsor, inline=True)
    if (url := thumbnail(config.thumbnail_url)) is not None:
        embed.set_thumbnail(url=url)
    embed.set_footer(text=texts.get("post.footer", {"ga@id": instance.id}))
    _fit(embed)
    return embed


def post_buttons(
    instance: Instance, texts: Texts, now: int, build_id: IdBuilder
) -> tuple[discord.ui.Button[discord.ui.View], ...]:
    """The post's join, draw and reroll buttons, the three ``ga@*-button`` models.

    Join / Leave is disabled once the giveaway is drawn or its end time has come, Draw Winners
    once drawn, and Reroll until drawn.
    """

    def button(
        style: discord.ButtonStyle, action: str, label: str, *, disabled: bool
    ) -> discord.ui.Button[discord.ui.View]:
        custom_id = build_id({"action": action, "giveaway_id": instance.id})
        return discord.ui.Button(style=style, custom_id=custom_id, label=label, disabled=disabled)

    closed = instance.ended or now >= instance.config.end_at
    return (
        button(discord.ButtonStyle.success, "participate", texts.get("post.join"), disabled=closed),
        button(
            discord.ButtonStyle.primary, "draw", texts.get("post.draw"), disabled=instance.ended
        ),
        button(
            discord.ButtonStyle.secondary,
            "reroll",
            texts.get("post.reroll"),
            disabled=not instance.ended,
        ),
    )


def result(instance: Instance, texts: Texts, *, reroll: bool) -> dict[str, str]:
    """The ``ga@header``, ``ga@body`` and ``ga@title`` of a draw's result.

    The body is the no participants text, or one winner line per prize clipped to 1800
    characters.
    """
    header = texts.get("result.rerolled" if reroll else "result.drawn")
    body = (
        clip(winner_lines(instance, texts), RESULT_MAX)
        if instance.participant_ids
        else texts.get("result.no-participants")
    )
    return {"ga@header": header, "ga@body": body, "ga@title": instance.config.title}


def winner_lines(instance: Instance, texts: Texts) -> str:
    """One ``prize: <@winner> ...`` line per prize, or the not enough text for none."""
    return "\n".join(
        f"{result.prize_name}: "
        + (" ".join(f"<@{winner}>" for winner in result.winner_ids) or texts.get("not-enough"))
        for result in instance.winner_results
    )


def _fit(embed: discord.Embed) -> None:
    """Shorten the description until the embed's texts hold at most 6000 UTF-16 code units."""
    parts = [embed.title, embed.description, embed.footer.text]
    parts += [part for field in embed.fields for part in (field.name, field.value)]
    excess = sum(units(part or "") for part in parts) - EMBED_MAX
    description = embed.description or ""
    if excess > 0:
        embed.description = clip(description, max(units(description) - excess, units(MORE)))
