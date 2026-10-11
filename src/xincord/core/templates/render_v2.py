"""Rendering Components V2 templates into discord.py layout items."""

import copy
from typing import TYPE_CHECKING, cast

import discord
from discord.ui.select import BaseSelect

from xincord.core.placeholders import render
from xincord.core.templates.base import (
    CHANNEL_TYPE_BY_NAME,
    TemplateError,
    custom_id,
    lookup,
    optional_text,
    resolve_emoji,
    resolve_model,
)
from xincord.core.templates.schema_v2 import (
    ActionRowV2,
    ButtonV2,
    ContainerV2,
    EmojiV2,
    EntitySelectV2,
    FileDisplayV2,
    MediaGalleryV2,
    ModelRefV2,
    SectionV2,
    SeparatorV2,
    StringSelectV2,
    TextDisplayV2,
    ThumbnailV2,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from xincord.core.templates.base import IdBuilder, Item
    from xincord.core.templates.schema_v2 import (
        AccessoryV2,
        ActionRowChildV2,
        MediaGalleryItemV2,
        OptionV2,
        TopLevelV2,
    )

type LayoutItem = discord.ui.Item[discord.ui.LayoutView]
type V2Spec = TopLevelV2 | AccessoryV2 | ActionRowChildV2

# Kinds of model each position accepts; an embed at the top level becomes a container.
TOP_LEVEL = (discord.ui.Item, discord.Embed)
ROW_ITEMS = (discord.ui.Button, BaseSelect)
BLANK = "_ _"  # Discord's idiom for an empty line
SELECTS = {
    frozenset({"USER"}): discord.ui.UserSelect[discord.ui.LayoutView],
    frozenset({"ROLE"}): discord.ui.RoleSelect[discord.ui.LayoutView],
    frozenset({"USER", "ROLE"}): discord.ui.MentionableSelect[discord.ui.LayoutView],
    frozenset({"CHANNEL"}): discord.ui.ChannelSelect[discord.ui.LayoutView],
}


def layout_view(
    components: Sequence[TopLevelV2],
    rows: Sequence[list[Item]],
    values: Mapping[str, str],
    build_id: IdBuilder | None,
    models: Mapping[str, object] | None,
) -> tuple[discord.ui.LayoutView, tuple[discord.File, ...]]:
    """Build a stopped layout view and the files it attaches.

    ``rows`` are rendered v1 rows; each becomes an action row.
    """
    renderer = _Renderer(values, build_id, models)
    view = discord.ui.LayoutView(timeout=None)
    for row in rows:
        view.add_item(discord.ui.ActionRow[discord.ui.LayoutView](*cast("list[LayoutItem]", row)))
    for spec in components:
        view.add_item(renderer.component(spec, *TOP_LEVEL))
    view.stop()
    return view, tuple(renderer.files)


def row_items(
    row: ActionRowV2,
    values: Mapping[str, str],
    build_id: IdBuilder | None,
    models: Mapping[str, object] | None,
) -> list[Item]:
    """Render the buttons and selects of a V2 action row for a message without V2 mode."""
    renderer = _Renderer(values, build_id, models)
    return [cast("Item", renderer.component(spec, *ROW_ITEMS)) for spec in row.components]


def _set_disabled(items: Iterable[LayoutItem], disabled: bool | None) -> None:  # noqa: FBT001
    """Enable or disable every button and select."""
    if disabled is None:
        return
    for item in items:
        if isinstance(item, discord.ui.Button | BaseSelect):
            item.disabled = disabled


def _with_default(option: discord.SelectOption, *, default: bool) -> discord.SelectOption:
    option = copy.copy(option)
    option.default = default
    return option


def _link(text: str, url: str | None) -> str:
    return f"[{text}]({url})" if url and url.strip() else text


def _embed_header(embed: discord.Embed) -> str:
    lines: list[str] = []
    if embed.author.name:
        lines.append("### " + _link(embed.author.name, embed.author.url))
    if embed.title and embed.title.strip():
        lines.append("## " + _link(embed.title, embed.url))
    if embed.description and embed.description.strip():
        lines.append(embed.description)
    return "\n".join(lines)


def _embed_container(embed: discord.Embed) -> LayoutItem:
    """Show an embed model as a container."""
    header = _embed_header(embed)
    children: list[LayoutItem] = []
    if thumbnail := embed.thumbnail.url or embed.author.icon_url:
        text = discord.ui.TextDisplay[discord.ui.LayoutView](header if header.strip() else BLANK)
        children.append(discord.ui.Section(text, accessory=discord.ui.Thumbnail(thumbnail)))
    elif header.strip():
        children.append(discord.ui.TextDisplay(header))
    for field in embed.fields:
        name, value = (field.name or "").strip(), (field.value or "").strip()
        if content := "\n".join(part for part in (f"**{name}**" if name else "", value) if part):
            children.append(discord.ui.TextDisplay(content))
    if embed.image.url:
        children.append(discord.ui.MediaGallery(discord.MediaGalleryItem(embed.image.url)))

    # Discord's timestamp markup shows the time in the reader's time zone.
    moment = f"<t:{int(embed.timestamp.timestamp())}:f>" if embed.timestamp else ""
    if footer := f" {chr(0x2022)} ".join(bit for bit in (embed.footer.text, moment) if bit):
        if children:
            children.append(discord.ui.Separator())
        children.append(discord.ui.TextDisplay(f"*{footer}*"))

    colour = embed.colour.value if embed.colour else None
    return discord.ui.Container(*children or [discord.ui.TextDisplay(BLANK)], accent_colour=colour)


class _Renderer:
    """Renders the V2 components of one message and collects the files they attach."""

    def __init__(
        self,
        values: Mapping[str, str],
        build_id: IdBuilder | None,
        models: Mapping[str, object] | None,
    ) -> None:
        self.values = values
        self.build_id = build_id
        self.models = models
        self.files: list[discord.File] = []

    def text(self, text: str) -> str:
        return render(text, self.values)

    def component(self, spec: V2Spec, *kinds: type[object]) -> LayoutItem:  # noqa: C901, PLR0911 - one case per type
        """Render ``spec``; a model must be one of ``kinds`` (any item by default)."""
        match spec:
            case ModelRefV2():
                return self.model(spec.model_key, kinds or (discord.ui.Item,))
            case ActionRowV2():
                children = [self.component(child, *ROW_ITEMS) for child in spec.components]
                return discord.ui.ActionRow[discord.ui.LayoutView](*children, id=spec.id)
            case SectionV2():
                return self.section(spec)
            case TextDisplayV2():
                return discord.ui.TextDisplay(self.text(spec.content), id=spec.id)
            case ThumbnailV2():
                return discord.ui.Thumbnail(
                    self.media(spec.file_path, spec.file_name, spec.url),
                    description=optional_text(spec.description, self.values),
                    spoiler=bool(spec.spoiler),
                    id=spec.id,
                )
            case MediaGalleryV2():
                items = [self.gallery_item(item) for item in spec.items]
                return discord.ui.MediaGallery(*items, id=spec.id)
            case SeparatorV2():
                spacing = discord.SeparatorSpacing[(spec.spacing or "small").lower()]
                return discord.ui.Separator(visible=spec.divider, spacing=spacing, id=spec.id)
            case FileDisplayV2():
                media = self.media(spec.file_path, spec.file_name, None)
                return discord.ui.File(media, spoiler=bool(spec.spoiler), id=spec.id)
            case ContainerV2():
                return self.container(spec)
            case ButtonV2():
                return self.button(spec)
            case StringSelectV2():
                return self.string_select(spec)
            case _:
                return self.entity_select(spec)

    def model(self, key: str, kinds: tuple[type[object], ...]) -> LayoutItem:
        model = lookup(self.models, key)
        if not isinstance(model, kinds):
            expected = " or ".join(kind.__name__ for kind in kinds)
            msg = f"model {key!r} is a {type(model).__name__}, expected {expected}"
            raise TemplateError(msg)
        if isinstance(model, discord.Embed):
            return _embed_container(model)
        return cast("LayoutItem", model)

    def section(self, spec: SectionV2) -> LayoutItem:
        children = [
            self.component(child, discord.ui.TextDisplay)
            for child in spec.components or spec.content
        ]
        accessory = self.component(spec.accessory, discord.ui.Button, discord.ui.Thumbnail)
        section = discord.ui.Section(*children, accessory=accessory, id=spec.id)
        _set_disabled(section.walk_children(), spec.disabled)
        return section

    def container(self, spec: ContainerV2) -> LayoutItem:
        container = discord.ui.Container(
            *(self.component(child) for child in spec.components),
            accent_colour=spec.accent_color,
            spoiler=bool(spec.spoiler),
            id=spec.id,
        )
        _set_disabled(container.walk_children(), spec.disabled)
        return container

    def media(self, file_path: str | None, file_name: str | None, url: str | None) -> str:
        """Return the URL of a media source; a ``file_path`` is attached to the message."""
        if file_path is not None:
            path = self.text(file_path)
            try:
                file = discord.File(path)
            except OSError as error:
                msg = f"cannot attach {path}: {error.strerror}"
                raise TemplateError(msg) from error
            self.files.append(file)
            return file.uri
        if file_name is not None:
            return f"attachment://{self.text(file_name)}"
        return self.text(url or "")

    def gallery_item(self, spec: MediaGalleryItemV2) -> discord.MediaGalleryItem:
        if spec.model_key is not None:
            return resolve_model(self.models, spec.model_key, discord.MediaGalleryItem)
        return discord.MediaGalleryItem(
            self.media(spec.file_path, spec.file_name, spec.url),
            description=optional_text(spec.description, self.values),
            spoiler=bool(spec.spoiler),
        )

    def emoji(self, spec: str | EmojiV2 | None) -> discord.PartialEmoji | str | None:
        if isinstance(spec, EmojiV2):
            text = spec.formatted or spec.name
            return resolve_emoji(spec.model_key, text, self.values, self.models)
        return resolve_emoji(None, spec, self.values, self.models)

    def custom_id(self, spec: ButtonV2 | StringSelectV2 | EntitySelectV2) -> str:
        if spec.custom_id is not None:
            return self.text(spec.custom_id)
        return custom_id(spec.uid, self.values, self.build_id)

    def button(self, spec: ButtonV2) -> LayoutItem:
        style = discord.ButtonStyle(spec.style_number)
        if style is discord.ButtonStyle.premium:
            # No label or emoji: Discord renders premium buttons from the SKU.
            sku = int(spec.sku or spec.sku_id or "")
            return discord.ui.Button(style=style, sku_id=sku, disabled=spec.disabled, id=spec.id)
        link = style is discord.ButtonStyle.link
        return discord.ui.Button(
            style=style,
            url=self.text(spec.url or "") if link else None,
            custom_id=None if link else self.custom_id(spec),
            label=optional_text(spec.label, self.values),
            emoji=self.emoji(spec.emoji),
            disabled=spec.disabled,
            id=spec.id,
        )

    def option(self, spec: OptionV2) -> discord.SelectOption:
        if spec.model_key is not None:
            return resolve_model(self.models, spec.model_key, discord.SelectOption)
        return discord.SelectOption(
            label=self.text(spec.label or ""),
            value=self.text(spec.value or ""),
            description=optional_text(spec.description, self.values),
            emoji=self.emoji(spec.emoji),
            default=bool(spec.default),
        )

    def string_select(self, spec: StringSelectV2) -> LayoutItem:
        options = [self.option(option) for option in spec.options]
        if spec.default_values:
            chosen = {self.text(value) for value in spec.default_values}
            options = [_with_default(option, default=option.value in chosen) for option in options]
        return discord.ui.Select(
            custom_id=self.custom_id(spec),
            placeholder=optional_text(spec.placeholder, self.values),
            min_values=spec.min,
            max_values=spec.max,
            options=options,
            disabled=bool(spec.disabled),
            id=spec.id,
        )

    def entity_select(self, spec: EntitySelectV2) -> LayoutItem:
        select = SELECTS[frozenset(spec.targets)](
            custom_id=self.custom_id(spec),
            placeholder=optional_text(spec.placeholder, self.values),
            min_values=spec.min,
            max_values=spec.max,
            disabled=bool(spec.disabled),
            default_values=[
                discord.SelectDefaultValue(
                    id=value.id, type=discord.SelectDefaultValueType[value.type.lower()]
                )
                for value in spec.default_values
            ],
            id=spec.id,
        )
        if isinstance(select, discord.ui.ChannelSelect):
            select.channel_types = [
                CHANNEL_TYPE_BY_NAME[name.upper()] for name in spec.channel_types
            ]
        return select
