"""Rendering parsed templates into discord.py objects."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast

import discord

from xincord.core.placeholders import render
from xincord.core.templates.base import (
    CHANNEL_TYPE_BY_NAME,
    COLOR,
    IdBuilder,
    Item,
    TemplateError,
    custom_id,
    lookup,
    optional_text,
    resolve_emoji,
    resolve_model,
    select_option,
)
from xincord.core.templates.render_v2 import layout_view, row_items
from xincord.core.templates.schema import ButtonsRow, StringSelectRow

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xincord.core.templates.schema import (
        ButtonSpec,
        EmbedSpec,
        EntitySelectRow,
        MessageTemplate,
        ModalTemplate,
        RowSpec,
        TextInputSpec,
    )
    from xincord.core.templates.schema_v2 import ActionRowV2

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
# JDA trimmed embed fields with Java's String.trim, which removes the characters up to U+0020.
JAVA_TRIM = "".join(map(chr, range(0x21)))
# JDA's EmbedBuilder.ZERO_WIDTH_SPACE, a left-to-right mark, replaced an empty field name or value,
# which Discord refuses.
EMPTY_FIELD = chr(0x200E)


@dataclass(frozen=True)
class EmbedField:
    """An embed field, for templates that insert fields through ``model_key``."""

    name: str
    value: str
    inline: bool = False


@dataclass(frozen=True)
class Message:
    """A rendered message: pass its parts to ``send`` or ``edit``."""

    content: str
    embeds: tuple[discord.Embed, ...] = ()
    view: discord.ui.View | discord.ui.LayoutView | None = None
    files: tuple[discord.File, ...] = ()


def render_message(
    template: MessageTemplate,
    values: Mapping[str, str],
    *,
    build_id: IdBuilder | None = None,
    models: Mapping[str, object] | None = None,
    now: datetime | None = None,
) -> Message:
    """Render a message template.

    Args:
        template: The parsed template.
        values: Placeholder values for this render only.
        build_id: Turns a rendered ``uid`` map into a component ID; required for components that
            are not links.
        models: Runtime objects for ``model_key`` entries.
        now: The time ``%now%`` stands for; defaults to the current time.

    Raises:
        TemplateError: A model is missing or of the wrong kind, a rendered color is invalid, or
            components need an ID builder that was not given.
    """
    if template.model_key is not None:
        return resolve_model(models, template.model_key, Message)
    moment = now or datetime.now(UTC)
    embeds = (_embed(spec, values, models, moment) for spec in template.embeds)
    v1_rows = () if template.components_v2 else template.components
    rows = [_row(row, values, build_id, models) for row in v1_rows]
    view: discord.ui.View | discord.ui.LayoutView | None = None
    files: tuple[discord.File, ...] = ()
    if template.is_components_v2:
        view, files = layout_view(template.components_v2, rows, values, build_id, models)
    else:
        rows += [
            row_items(cast("ActionRowV2", row), values, build_id, models)
            for row in template.components_v2
        ]
        view = _view(rows) if rows else None
    return Message(
        content=render(template.content, values),
        embeds=tuple(embed for embed in embeds if embed is not None),
        view=view,
        files=files,
    )


def _embed(
    spec: EmbedSpec,
    values: Mapping[str, str],
    models: Mapping[str, object] | None,
    moment: datetime,
) -> discord.Embed | None:
    if spec.model_key is not None:
        return resolve_model(models, spec.model_key, discord.Embed)

    def link(url: str | None) -> str | None:
        rendered = render(url, values) if url is not None else ""
        return rendered if rendered.startswith("http") else None

    embed = discord.Embed(
        title=render(spec.title.text, values) if spec.title else None,
        url=link(spec.title.url) if spec.title else None,
        description=render(spec.description, values) if spec.description else None,
        colour=_color(spec.color_code, values),
        timestamp=_timestamp(spec.timestamp, moment),
    )
    if spec.author:
        embed.set_author(
            name=render(spec.author.name, values),
            url=link(spec.author.url),
            icon_url=link(spec.author.icon_url),
        )
    if thumbnail := link(spec.thumbnail_url):
        embed.set_thumbnail(url=thumbnail)
    if image := link(spec.image_url):
        embed.set_image(url=image)
    if spec.footer:
        embed.set_footer(text=render(spec.footer.text, values), icon_url=link(spec.footer.icon_url))
    for field in spec.fields:
        if field.model_key is not None:
            model = resolve_model(models, field.model_key, EmbedField)
            name, value, inline = model.name, model.value, model.inline
        else:
            name, value = render(field.name or "", values), render(field.value or "", values)
            inline = field.inline
        embed.add_field(name=_field_text(name), value=_field_text(value), inline=inline)
    return embed if _has_content(embed) else None


def _field_text(text: str) -> str:
    """Return a field's name or value as JDA's ``MessageEmbed.Field`` kept it."""
    return text.strip(JAVA_TRIM) or EMPTY_FIELD


def _has_content(embed: discord.Embed) -> bool:
    """Mirror JDA's ``EmbedBuilder.isEmpty()``: a color alone does not count."""
    return any(
        (
            embed.title,
            embed.description,
            embed.timestamp,
            embed.thumbnail.url,
            embed.author.name,
            embed.footer.text,
            embed.image.url,
            embed.fields,
        ),
    )


def _color(code: str | None, values: Mapping[str, str]) -> int | None:
    if code is None:
        return None
    rendered = render(code, values)
    if not COLOR.fullmatch(rendered):
        msg = f"color_code {rendered!r} is not #RRGGBB or 0xRRGGBB"
        raise TemplateError(msg)
    return int(rendered[1:] if rendered.startswith("#") else rendered[2:], 16)


def _timestamp(text: str | None, moment: datetime) -> datetime | None:
    if text is None:
        return None
    return moment if text == "%now%" else EPOCH + timedelta(milliseconds=int(text))


def _view(rows: Sequence[list[Item]]) -> discord.ui.View:
    """Build a stopped view, so discord.py sends it but never dispatches its interactions."""
    view = discord.ui.View(timeout=None)
    for index, row in enumerate(rows):
        for item in row:
            item.row = index
            view.add_item(item)
    view.stop()
    return view


def _row(
    row: RowSpec,
    values: Mapping[str, str],
    build_id: IdBuilder | None,
    models: Mapping[str, object] | None,
) -> list[Item]:
    if row.model_key is not None:
        model = lookup(models, row.model_key)
        items = list(cast("Sequence[object]", model)) if isinstance(model, list | tuple) else []
        if not items or not all(isinstance(item, discord.ui.Item) for item in items):
            msg = f"model {row.model_key!r} must be a non-empty list of components"
            raise TemplateError(msg)
        return cast("list[Item]", items)
    match row:
        case ButtonsRow():
            return [_button(spec, values, build_id, models) for spec in row.buttons]
        case StringSelectRow():
            return [_string_select(row, values, build_id, models)]
        case _:
            return [_entity_select(row, values, build_id)]


def _button(
    spec: ButtonSpec,
    values: Mapping[str, str],
    build_id: IdBuilder | None,
    models: Mapping[str, object] | None,
) -> Item:
    if spec.model_key is not None:
        model = lookup(models, spec.model_key)
        if not isinstance(model, discord.ui.Button):
            msg = f"model {spec.model_key!r} is a {type(model).__name__}, expected Button"
            raise TemplateError(msg)
        return cast("Item", model)
    emoji = (
        resolve_emoji(spec.emoji.model_key, spec.emoji.formatted, values, models)
        if spec.emoji
        else None
    )
    label = optional_text(spec.label, values)
    if spec.style == discord.ButtonStyle.link.value:
        return discord.ui.Button[discord.ui.View](
            style=discord.ButtonStyle.link,
            url=render(spec.url or "", values),
            label=label,
            emoji=emoji,
            disabled=spec.disabled,
        )
    return discord.ui.Button[discord.ui.View](
        style=discord.ButtonStyle(spec.style),
        custom_id=custom_id(spec.uid, values, build_id),
        label=label,
        emoji=emoji,
        disabled=spec.disabled,
    )


def _string_select(
    row: StringSelectRow,
    values: Mapping[str, str],
    build_id: IdBuilder | None,
    models: Mapping[str, object] | None,
) -> Item:
    options = [select_option(spec, values, models) for spec in row.options]
    return discord.ui.Select[discord.ui.View](
        custom_id=custom_id(row.uid, values, build_id),
        placeholder=optional_text(row.placeholder, values),
        min_values=row.min,
        max_values=row.max,
        options=options,
    )


def _entity_select(
    row: EntitySelectRow, values: Mapping[str, str], build_id: IdBuilder | None
) -> Item:
    component_id = custom_id(row.uid, values, build_id)
    placeholder = optional_text(row.placeholder, values)
    match (row.select_target_type or "").upper():
        case "USER":
            return discord.ui.UserSelect[discord.ui.View](
                custom_id=component_id,
                placeholder=placeholder,
                min_values=row.min,
                max_values=row.max,
            )
        case "ROLE":
            return discord.ui.RoleSelect[discord.ui.View](
                custom_id=component_id,
                placeholder=placeholder,
                min_values=row.min,
                max_values=row.max,
            )
        case _:
            return discord.ui.ChannelSelect[discord.ui.View](
                custom_id=component_id,
                placeholder=placeholder,
                min_values=row.min,
                max_values=row.max,
                channel_types=[CHANNEL_TYPE_BY_NAME[name.upper()] for name in row.channel_types],
            )


def render_modal(
    template: ModalTemplate,
    values: Mapping[str, str],
    *,
    build_id: IdBuilder | None,
    models: Mapping[str, object] | None = None,
) -> discord.ui.Modal:
    """Render a modal template into a stopped modal whose ID comes from ``build_id``.

    Raises:
        TemplateError: A model is missing or of the wrong kind, or ``build_id`` is None.
    """
    if template.model_key is not None:
        return resolve_model(models, template.model_key, discord.ui.Modal)
    modal = discord.ui.Modal(
        title=render(template.title or "", values),
        custom_id=custom_id(template.uid, values, build_id),
        timeout=None,
    )
    for spec in template.text_inputs:
        # A Label carries the input's title, as JDA 6's Label.of did in v3.
        label = discord.ui.Label[discord.ui.Modal](
            text=render(spec.label, values),
            component=_text_input(spec, values, models),
        )
        modal.add_item(label)
    modal.stop()
    return modal


def _text_input(
    spec: TextInputSpec,
    values: Mapping[str, str],
    models: Mapping[str, object] | None,
) -> discord.ui.TextInput[discord.ui.Modal]:
    if spec.model_key is not None:
        model = lookup(models, spec.model_key)
        if not isinstance(model, discord.ui.TextInput):
            msg = f"model {spec.model_key!r} is a {type(model).__name__}, expected TextInput"
            raise TemplateError(msg)
        return cast("discord.ui.TextInput[discord.ui.Modal]", model)
    value = render(spec.value or "", values)
    placeholder = render(spec.placeholder or "", values)
    return discord.ui.TextInput[discord.ui.Modal](
        custom_id=render(spec.uid or "", values),
        style=discord.TextStyle.paragraph if spec.style == "PARAGRAPH" else discord.TextStyle.short,
        default=value if value.strip() else None,
        placeholder=placeholder if placeholder.strip() else None,
        min_length=spec.min_length if spec.min_length >= 0 else None,
        max_length=spec.max_length if spec.max_length >= 0 else None,
        required=spec.required,
    )
