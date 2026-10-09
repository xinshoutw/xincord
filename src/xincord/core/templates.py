"""Message and modal templates: YAML loading, validation and rendering to discord.py objects."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated, Literal, Self, cast

import discord
import yaml
from pydantic import ConfigDict, Field, model_validator

from xincord.core.config import Model, parse_model
from xincord.core.placeholders import CHANNEL_TYPES, render

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path

    from xincord.core.i18n import Lang

COLOR = re.compile(r"(?:#|0[xX])[0-9a-fA-F]{1,6}")
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
ENTITY_TARGETS = ("USER", "ROLE", "CHANNEL")
# JDA channel type names that discord.py can put in a channel select.
CHANNEL_TYPE_BY_NAME = {
    name: discord.ChannelType(value)
    for value, name in CHANNEL_TYPES.items()
    if value in {kind.value for kind in discord.ChannelType}
}


class TemplateError(Exception):
    """A template is malformed or cannot be rendered; the message names the file or key."""


class TemplateModel(Model):
    """Base of the template schemas: numbers in text fields stay text, as in v3's KAML."""

    model_config = ConfigDict(extra="allow", frozen=True, coerce_numbers_to_str=True)


def _require(model: TemplateModel, *names: str) -> None:
    """Fail unless every field in ``names`` is set, or the model is replaced by a ``model_key``."""
    if getattr(model, "model_key", None) is not None:
        return
    if missing := [name for name in names if getattr(model, name) is None]:
        msg = f"needs {', '.join(missing)} unless model_key is set"
        raise ValueError(msg)


class AuthorSpec(TemplateModel):
    """An embed author."""

    name: str
    url: str | None = None
    icon_url: str | None = None


class TitleSpec(TemplateModel):
    """An embed title with an optional link."""

    text: str
    url: str | None = None


class FooterSpec(TemplateModel):
    """An embed footer."""

    text: str
    icon_url: str | None = None


class FieldSpec(TemplateModel):
    """An embed field, or a ``model_key`` for an :class:`EmbedField`."""

    model_key: str | None = None
    name: str | None = None
    value: str | None = None
    inline: bool = False

    @model_validator(mode="after")
    def _complete(self) -> Self:
        _require(self, "name", "value")
        return self


class EmbedSpec(TemplateModel):
    """An embed, or a ``model_key`` for a :class:`discord.Embed`."""

    model_key: str | None = None
    author: AuthorSpec | None = None
    title: TitleSpec | None = None
    description: str | None = None
    thumbnail_url: str | None = None
    image_url: str | None = None
    color_code: str | None = None
    footer: FooterSpec | None = None
    timestamp: str | None = None
    fields: tuple[FieldSpec, ...] = ()

    @model_validator(mode="after")
    def _formats(self) -> Self:
        color = self.color_code
        if color is not None and "%" not in color and not COLOR.fullmatch(color):
            msg = f"color_code {color!r} is not #RRGGBB or 0xRRGGBB"
            raise ValueError(msg)
        if self.timestamp is not None and not (
            self.timestamp == "%now%" or self.timestamp.isdigit()
        ):
            msg = f"timestamp {self.timestamp!r} is neither %now% nor epoch milliseconds"
            raise ValueError(msg)
        return self


class ButtonEmojiSpec(TemplateModel):
    """A button emoji: ``formatted`` text or a ``model_key``."""

    model_key: str | None = None
    formatted: str | None = None

    @model_validator(mode="after")
    def _one_source(self) -> Self:
        if (self.model_key is None) == (self.formatted is None):
            msg = "set exactly one of formatted and model_key"
            raise ValueError(msg)
        return self


class ButtonSpec(TemplateModel):
    """A button: style 5 links to ``url``; the other styles carry an ID built from ``uid``."""

    model_key: str | None = None
    uid: dict[str, str] | None = None
    url: str | None = None
    style: Annotated[int, Field(ge=1, le=5)] = 1
    label: str | None = None
    disabled: bool = False
    emoji: ButtonEmojiSpec | None = None

    @model_validator(mode="after")
    def _target(self) -> Self:
        _require(self, "url" if self.style == 5 else "uid")  # noqa: PLR2004 - link style
        return self


class ButtonsRow(TemplateModel):
    """A row of buttons (YAML tag ``!ButtonsComponent``)."""

    type: Literal["buttons"]
    model_key: str | None = None
    buttons: tuple[ButtonSpec, ...] = ()


class OptionEmojiSpec(TemplateModel):
    """A select option emoji."""

    model_key: str | None = None
    name: str | None = None
    animated: bool = False

    @model_validator(mode="after")
    def _complete(self) -> Self:
        _require(self, "name")
        return self


class OptionSpec(TemplateModel):
    """A string select option."""

    model_key: str | None = None
    label: str | None = None
    value: str | None = None
    description: str | None = None
    default: bool = False
    emoji: OptionEmojiSpec | None = None

    @model_validator(mode="after")
    def _complete(self) -> Self:
        _require(self, "label", "value")
        return self


class StringSelectRow(TemplateModel):
    """A string select (YAML tag ``!StringSelectMenu``)."""

    type: Literal["string_select"]
    model_key: str | None = None
    uid: dict[str, str] | None = None
    placeholder: str | None = None
    min: int = 1
    max: int = 1
    options: tuple[OptionSpec, ...] = ()

    @model_validator(mode="after")
    def _complete(self) -> Self:
        _require(self, "uid")
        return self


class EntitySelectRow(TemplateModel):
    """A user, role or channel select (YAML tag ``!EntitySelectMenu``)."""

    type: Literal["entity_select"]
    model_key: str | None = None
    uid: dict[str, str] | None = None
    placeholder: str | None = None
    min: int = 1
    max: int = 1
    select_target_type: str | None = None
    channel_types: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _target(self) -> Self:
        _require(self, "uid", "select_target_type")
        if self.model_key is not None or self.select_target_type is None:
            return self
        target = self.select_target_type.upper()
        if target not in ENTITY_TARGETS:
            msg = f"select_target_type must be one of {', '.join(ENTITY_TARGETS)}"
            raise ValueError(msg)
        if target == "CHANNEL" and not self.channel_types:
            msg = "channel_types is required when select_target_type is CHANNEL"
            raise ValueError(msg)
        if unknown := [
            kind for kind in self.channel_types if kind.upper() not in CHANNEL_TYPE_BY_NAME
        ]:
            msg = f"unknown channel types {unknown}"
            raise ValueError(msg)
        return self


type RowSpec = Annotated[
    ButtonsRow | StringSelectRow | EntitySelectRow, Field(discriminator="type")
]


class MessageTemplate(TemplateModel):
    """A parsed message template."""

    model_key: str | None = None
    content: str = ""
    embeds: tuple[EmbedSpec, ...] = ()
    components: tuple[RowSpec, ...] = ()


class TextInputSpec(TemplateModel):
    """A modal text input."""

    model_key: str | None = None
    label: str
    uid: str | None = None
    value: str | None = None
    placeholder: str | None = None
    min_length: int = -1
    max_length: int = -1
    style: Literal["SHORT", "PARAGRAPH"] | None = None
    required: bool = True

    @model_validator(mode="after")
    def _complete(self) -> Self:
        _require(self, "uid", "style")
        return self


class ModalTemplate(TemplateModel):
    """A parsed modal template."""

    model_key: str | None = None
    uid: dict[str, str] | None = None
    title: str | None = None
    text_inputs: tuple[TextInputSpec, ...] = ()

    @model_validator(mode="after")
    def _complete(self) -> Self:
        _require(self, "uid", "title")
        return self


class _Loader(yaml.SafeLoader):
    """A safe loader that also understands v3's component tags."""


def _tagged(kind: str) -> Callable[[yaml.SafeLoader, yaml.Node], dict[object, object]]:
    def construct(loader: yaml.SafeLoader, node: yaml.Node) -> dict[object, object]:
        if not isinstance(node, yaml.MappingNode):
            msg = f"{node.tag} must be a mapping"
            raise yaml.constructor.ConstructorError(None, None, msg, node.start_mark)
        return {**loader.construct_mapping(node, deep=True), "type": kind}

    return construct


for _tag, _kind in (
    ("!ButtonsComponent", "buttons"),
    ("!StringSelectMenu", "string_select"),
    ("!EntitySelectMenu", "entity_select"),
):
    _Loader.add_constructor(_tag, _tagged(_kind))


def _load[T: TemplateModel](path: Path, model: type[T]) -> T:
    try:
        data: object = yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader)  # noqa: S506 - a SafeLoader subclass
    except (OSError, yaml.YAMLError) as error:
        msg = f"{path}: {error}"
        raise TemplateError(msg) from error
    return parse_model(path, data, model, TemplateError)


def load_message(path: Path) -> MessageTemplate:
    """Parse and validate a message template, warning about unknown keys.

    Raises:
        TemplateError: The file is not valid YAML or not a valid template.
    """
    return _load(path, MessageTemplate)


def load_modal(path: Path) -> ModalTemplate:
    """Parse and validate a modal template, warning about unknown keys.

    Raises:
        TemplateError: The file is not valid YAML or not a valid template.
    """
    return _load(path, ModalTemplate)


class Templates:
    """Every message and modal template of one plugin, parsed when the plugin loads."""

    def __init__(
        self,
        lang: Lang,
        messages: dict[Path, MessageTemplate],
        modals: dict[Path, ModalTemplate],
    ) -> None:
        """Wrap parsed templates; use :meth:`load` instead."""
        self._lang = lang
        self._messages = messages
        self._modals = modals

    @classmethod
    def load(cls, lang: Lang) -> Self:
        """Load every template of every locale in ``lang``.

        Raises:
            TemplateError: A template is malformed.
        """
        messages: dict[Path, MessageTemplate] = {}
        modals: dict[Path, ModalTemplate] = {}
        for table in lang.templates.values():
            for name, path in table.items():
                if name.startswith("message/"):
                    messages[path] = load_message(path)
                else:
                    modals[path] = load_modal(path)
        return cls(lang, messages, modals)

    def message(self, name: str, locale: str) -> MessageTemplate:
        """Return message template ``name`` in ``locale``, else in the default locale."""
        return self._messages[self._lang.template(f"message/{name}", locale)]

    def modal(self, name: str, locale: str) -> ModalTemplate:
        """Return modal template ``name`` in ``locale``, else in the default locale."""
        return self._modals[self._lang.template(f"modal/{name}", locale)]


type IdBuilder = Callable[[Mapping[str, str]], str]


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
    view: discord.ui.View | None = None


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
        return _model(models, template.model_key, Message)
    moment = now or datetime.now(UTC)
    embeds = (_embed(spec, values, models, moment) for spec in template.embeds)
    view = _view(template.components, values, build_id, models) if template.components else None
    return Message(
        content=render(template.content, values),
        embeds=tuple(embed for embed in embeds if embed is not None),
        view=view,
    )


def _embed(
    spec: EmbedSpec,
    values: Mapping[str, str],
    models: Mapping[str, object] | None,
    moment: datetime,
) -> discord.Embed | None:
    if spec.model_key is not None:
        return _model(models, spec.model_key, discord.Embed)

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
            model = _model(models, field.model_key, EmbedField)
            embed.add_field(name=model.name, value=model.value, inline=model.inline)
        else:
            name, value = render(field.name or "", values), render(field.value or "", values)
            embed.add_field(name=name, value=value, inline=field.inline)
    return embed if _has_content(embed) else None


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


def _lookup(models: Mapping[str, object] | None, key: str) -> object:
    # ponytail: model keys are looked up verbatim, as v3 did, even when they contain %...%.
    if models is None or key not in models:
        msg = f"no model named {key!r} was supplied"
        raise TemplateError(msg)
    return models[key]


def _model[T](models: Mapping[str, object] | None, key: str, kind: type[T]) -> T:
    model = _lookup(models, key)
    if not isinstance(model, kind):
        msg = f"model {key!r} is a {type(model).__name__}, expected {kind.__name__}"
        raise TemplateError(msg)
    return model


type Item = discord.ui.Item[discord.ui.View]


def _view(
    rows: tuple[RowSpec, ...],
    values: Mapping[str, str],
    build_id: IdBuilder | None,
    models: Mapping[str, object] | None,
) -> discord.ui.View:
    """Build a stopped view, so discord.py sends it but never dispatches its interactions."""
    view = discord.ui.View(timeout=None)
    for index, row in enumerate(rows):
        for item in _row(row, values, build_id, models):
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
        model = _lookup(models, row.model_key)
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


def _id(
    uid: Mapping[str, str] | None, values: Mapping[str, str], build_id: IdBuilder | None
) -> str:
    if build_id is None:
        msg = "components with a uid need an ID builder"
        raise TemplateError(msg)
    return build_id({key: render(value, values) for key, value in (uid or {}).items()})


def _text(text: str | None, values: Mapping[str, str]) -> str | None:
    return None if text is None else render(text, values)


def _emoji(
    model_key: str | None,
    formatted: str | None,
    values: Mapping[str, str],
    models: Mapping[str, object] | None,
) -> discord.PartialEmoji | str | None:
    if model_key is not None:
        model = _lookup(models, model_key)
        if not isinstance(model, discord.PartialEmoji | str):
            msg = f"model {model_key!r} is a {type(model).__name__}, expected an emoji"
            raise TemplateError(msg)
        return model
    return None if formatted is None else discord.PartialEmoji.from_str(render(formatted, values))


def _button(
    spec: ButtonSpec,
    values: Mapping[str, str],
    build_id: IdBuilder | None,
    models: Mapping[str, object] | None,
) -> Item:
    if spec.model_key is not None:
        model = _lookup(models, spec.model_key)
        if not isinstance(model, discord.ui.Button):
            msg = f"model {spec.model_key!r} is a {type(model).__name__}, expected Button"
            raise TemplateError(msg)
        return cast("Item", model)
    emoji = (
        _emoji(spec.emoji.model_key, spec.emoji.formatted, values, models) if spec.emoji else None
    )
    label = _text(spec.label, values)
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
        custom_id=_id(spec.uid, values, build_id),
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
    options = [_option(spec, values, models) for spec in row.options]
    return discord.ui.Select[discord.ui.View](
        custom_id=_id(row.uid, values, build_id),
        placeholder=_text(row.placeholder, values),
        min_values=row.min,
        max_values=row.max,
        options=options,
    )


def _option(
    spec: OptionSpec,
    values: Mapping[str, str],
    models: Mapping[str, object] | None,
) -> discord.SelectOption:
    if spec.model_key is not None:
        return _model(models, spec.model_key, discord.SelectOption)
    emoji = _emoji(spec.emoji.model_key, spec.emoji.name, values, models) if spec.emoji else None
    return discord.SelectOption(
        label=render(spec.label or "", values),
        value=render(spec.value or "", values),
        description=_text(spec.description, values),
        emoji=emoji,
        default=spec.default,
    )


def _entity_select(
    row: EntitySelectRow, values: Mapping[str, str], build_id: IdBuilder | None
) -> Item:
    custom_id = _id(row.uid, values, build_id)
    placeholder = _text(row.placeholder, values)
    match (row.select_target_type or "").upper():
        case "USER":
            return discord.ui.UserSelect[discord.ui.View](
                custom_id=custom_id,
                placeholder=placeholder,
                min_values=row.min,
                max_values=row.max,
            )
        case "ROLE":
            return discord.ui.RoleSelect[discord.ui.View](
                custom_id=custom_id,
                placeholder=placeholder,
                min_values=row.min,
                max_values=row.max,
            )
        case _:
            return discord.ui.ChannelSelect[discord.ui.View](
                custom_id=custom_id,
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
        return _model(models, template.model_key, discord.ui.Modal)
    modal = discord.ui.Modal(
        title=render(template.title or "", values),
        custom_id=_id(template.uid, values, build_id),
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
        model = _lookup(models, spec.model_key)
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
