"""Template schemas and the YAML loader."""

from typing import TYPE_CHECKING, Annotated, Literal, Self

import yaml
from pydantic import Field, model_validator

from xincord.core.config import parse_model
from xincord.core.templates.base import (
    CHANNEL_TYPE_BY_NAME,
    COLOR,
    ENTITY_TARGETS,
    TemplateError,
    TemplateModel,
    require,
)
from xincord.core.templates.schema_v2 import ActionRowV2, ModelRefV2, TopLevelV2

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


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
        require(self, "name", "value")
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
        require(self, "url" if self.style == 5 else "uid")  # noqa: PLR2004 - link style
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
        require(self, "name")
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
        require(self, "label", "value")
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
        require(self, "uid")
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
        require(self, "uid", "select_target_type")
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
    is_components_v2: bool = False
    components_v2: tuple[TopLevelV2, ...] = ()

    @model_validator(mode="after")
    def _v2_mode(self) -> Self:
        if not self.is_components_v2:
            if any(not isinstance(item, ActionRowV2 | ModelRefV2) for item in self.components_v2):
                msg = "components_v2 holds only action rows unless is_components_v2 is true"
                raise ValueError(msg)
        elif self.content.strip() or self.embeds:
            msg = "content and embeds must be empty when is_components_v2 is true"
            raise ValueError(msg)
        elif not (self.components or self.components_v2):
            msg = "is_components_v2 needs at least one component"
            raise ValueError(msg)
        return self


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
        require(self, "uid", "style")
        return self


class ModalTemplate(TemplateModel):
    """A parsed modal template."""

    model_key: str | None = None
    uid: dict[str, str] | None = None
    title: str | None = None
    text_inputs: tuple[TextInputSpec, ...] = ()

    @model_validator(mode="after")
    def _complete(self) -> Self:
        require(self, "uid", "title")
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
