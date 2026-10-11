"""Components V2 template schema (``components_v2`` entries)."""

from typing import Annotated, Self, cast

from pydantic import Discriminator, Tag, field_validator, model_validator

from xincord.core.templates.base import (
    CHANNEL_TYPE_BY_NAME,
    COLOR,
    ENTITY_TARGETS,
    TemplateModel,
    require,
)

TYPE_ALIASES = {"string_select_menu": "string_select", "entity_select_menu": "entity_select"}
BUTTON_STYLES = {
    "PRIMARY": 1,
    "BLUE": 1,
    "SECONDARY": 2,
    "GRAY": 2,
    "GREY": 2,
    "SUCCESS": 3,
    "GREEN": 3,
    "DANGER": 4,
    "RED": 4,
    "LINK": 5,
    "PREMIUM": 6,
}
LINK, PREMIUM = BUTTON_STYLES["LINK"], BUTTON_STYLES["PREMIUM"]
SPACINGS = ("SMALL", "LARGE")
# discord.py has a select class for each of these target sets.
TARGET_SETS = ({"USER"}, {"ROLE"}, {"USER", "ROLE"}, {"CHANNEL"})


def _field(data: object, name: str) -> object:
    if isinstance(data, dict):
        return cast("dict[str, object]", data).get(name)
    return getattr(data, name, None)


def component_type(data: object) -> str | None:
    """Return a V2 component's normalized ``type``, or ``model`` when it has a ``model_key``."""
    if _field(data, "model_key") is not None:
        return "model"
    raw = _field(data, "type")
    if not isinstance(raw, str):
        return None
    kind = raw.lower().replace("-", "_")
    return TYPE_ALIASES.get(kind, kind)


def accessory_type(data: object) -> str | None:
    """Like :func:`component_type`, inferring a missing type."""
    if _field(data, "type") is not None or _field(data, "model_key") is not None:
        return component_type(data)
    has_media = any(_field(data, name) is not None for name in ("url", "file_path", "file_name"))
    return "thumbnail" if has_media else "button"


class V2Model(TemplateModel):
    """Fields every V2 component accepts."""

    type: str | None = None
    id: int | None = None


class ModelRefV2(V2Model):
    """A component replaced by the model supplied under ``model_key``."""

    model_key: str


class EmojiV2(TemplateModel):
    """An emoji object: ``formatted`` or ``name`` text, or a ``model_key``."""

    model_key: str | None = None
    formatted: str | None = None
    name: str | None = None

    @model_validator(mode="after")
    def _complete(self) -> Self:
        if self.model_key is None and self.formatted is None and self.name is None:
            msg = "an emoji needs formatted, name or model_key"
            raise ValueError(msg)
        return self


class ButtonV2(V2Model):
    """A V2 button: style by number or name; links need ``url``, premium buttons a SKU."""

    style: int | str = 1
    label: str | None = None
    emoji: str | EmojiV2 | None = None
    disabled: bool = False
    url: str | None = None
    sku: str | None = None
    sku_id: str | None = None
    uid: dict[str, str] | None = None
    custom_id: str | None = None

    @property
    def style_number(self) -> int:
        """The style as Discord's number (1 to 6)."""
        style = self.style
        return style if isinstance(style, int) else BUTTON_STYLES[style.upper()]

    @model_validator(mode="after")
    def _target(self) -> Self:
        known = (
            self.style in BUTTON_STYLES.values()
            if isinstance(self.style, int)
            else self.style.upper() in BUTTON_STYLES
        )
        if not known:
            msg = f"unknown button style {self.style!r}"
            raise ValueError(msg)
        if self.style_number == LINK:
            require(self, "url")
        elif self.style_number == PREMIUM:
            if not (self.sku or self.sku_id or "").isdigit():
                msg = "a premium button needs a numeric sku or sku_id"
                raise ValueError(msg)
        elif self.custom_id is None and self.uid is None:
            msg = "needs custom_id or uid"
            raise ValueError(msg)
        return self


class OptionV2(TemplateModel):
    """A V2 string select option, or a ``model_key``."""

    model_key: str | None = None
    label: str | None = None
    value: str | None = None
    description: str | None = None
    default: bool | None = None
    emoji: str | EmojiV2 | None = None

    @model_validator(mode="after")
    def _complete(self) -> Self:
        require(self, "label", "value")
        return self


class _SelectV2(V2Model):
    uid: dict[str, str] | None = None
    custom_id: str | None = None
    placeholder: str | None = None
    min: int = 1
    max: int = 1
    disabled: bool | None = None

    @model_validator(mode="after")
    def _identified(self) -> Self:
        if self.custom_id is None and self.uid is None:
            msg = "needs custom_id or uid"
            raise ValueError(msg)
        return self


class StringSelectV2(_SelectV2):
    """A V2 string select; ``default_values`` preselects options by value."""

    options: tuple[OptionV2, ...] = ()
    default_values: tuple[str, ...] = ()


class DefaultValueV2(TemplateModel):
    """A preselected entity of an entity select."""

    id: int
    type: str

    @field_validator("type")
    @classmethod
    def _known(cls, value: str) -> str:
        if value.upper() not in ENTITY_TARGETS:
            msg = f"default value type must be one of {', '.join(ENTITY_TARGETS)}"
            raise ValueError(msg)
        return value.upper()


class EntitySelectV2(_SelectV2):
    """A V2 user, role, mentionable or channel select."""

    select_targets: tuple[str, ...] = ()
    select_target_type: str | None = None
    channel_types: tuple[str, ...] = ()
    default_values: tuple[DefaultValueV2, ...] = ()

    @property
    def targets(self) -> set[str]:
        """The target kinds, upper case; ``select_targets`` wins over ``select_target_type``."""
        names = self.select_targets or (self.select_target_type,)
        return {name.upper() for name in names if name}

    @model_validator(mode="after")
    def _targets(self) -> Self:
        if self.targets not in TARGET_SETS:
            msg = "select_targets must be USER, ROLE, USER and ROLE, or CHANNEL"
            raise ValueError(msg)
        if unknown := [
            kind for kind in self.channel_types if kind.upper() not in CHANNEL_TYPE_BY_NAME
        ]:
            msg = f"unknown channel types {unknown}"
            raise ValueError(msg)
        return self


type ActionRowChildV2 = Annotated[
    Annotated[ButtonV2, Tag("button")]
    | Annotated[StringSelectV2, Tag("string_select")]
    | Annotated[EntitySelectV2, Tag("entity_select")]
    | Annotated[ModelRefV2, Tag("model")],
    Discriminator(component_type),
]


class ActionRowV2(V2Model):
    """A V2 action row."""

    components: tuple[ActionRowChildV2, ...] = ()


class TextDisplayV2(V2Model):
    """Markdown text."""

    content: str


class _MediaFields(TemplateModel):
    model_key: str | None = None
    url: str | None = None
    file_path: str | None = None
    file_name: str | None = None
    description: str | None = None
    spoiler: bool | None = None

    @model_validator(mode="after")
    def _source(self) -> Self:
        sources = (self.url, self.file_path, self.file_name)
        if self.model_key is None and all(source is None for source in sources):
            msg = "needs url, file_path or file_name"
            raise ValueError(msg)
        return self


class ThumbnailV2(V2Model, _MediaFields):
    """A section thumbnail."""


class MediaGalleryItemV2(_MediaFields):
    """One media gallery item, or a ``model_key``."""


class MediaGalleryV2(V2Model):
    """A media gallery."""

    items: tuple[MediaGalleryItemV2, ...] = ()


class SeparatorV2(V2Model):
    """A separator."""

    spacing: str | None = None
    divider: bool = True

    @field_validator("spacing")
    @classmethod
    def _known(cls, value: str | None) -> str | None:
        if value is not None and value.upper() not in SPACINGS:
            msg = f"unknown separator spacing {value!r}"
            raise ValueError(msg)
        return value


class FileDisplayV2(V2Model):
    """An attached file."""

    file_path: str | None = None
    file_name: str | None = None
    spoiler: bool | None = None

    @model_validator(mode="after")
    def _source(self) -> Self:
        if self.file_path is None and self.file_name is None:
            msg = "needs file_path or file_name"
            raise ValueError(msg)
        return self


type SectionContentV2 = Annotated[
    Annotated[TextDisplayV2, Tag("text_display")] | Annotated[ModelRefV2, Tag("model")],
    Discriminator(component_type),
]
type AccessoryV2 = Annotated[
    Annotated[ButtonV2, Tag("button")]
    | Annotated[ThumbnailV2, Tag("thumbnail")]
    | Annotated[ModelRefV2, Tag("model")],
    Discriminator(accessory_type),
]


class SectionV2(V2Model):
    """Text with a button or thumbnail beside it; ``content`` is an alias of ``components``."""

    components: tuple[SectionContentV2, ...] = ()
    content: tuple[SectionContentV2, ...] = ()
    accessory: AccessoryV2
    disabled: bool | None = None


type ContainerChildV2 = Annotated[
    Annotated[ActionRowV2, Tag("action_row")]
    | Annotated[SectionV2, Tag("section")]
    | Annotated[TextDisplayV2, Tag("text_display")]
    | Annotated[MediaGalleryV2, Tag("media_gallery")]
    | Annotated[SeparatorV2, Tag("separator")]
    | Annotated[FileDisplayV2, Tag("file_display")]
    | Annotated[ModelRefV2, Tag("model")],
    Discriminator(component_type),
]


class ContainerV2(V2Model):
    """A container with an optional accent color."""

    components: tuple[ContainerChildV2, ...] = ()
    accent_color: int | None = None
    spoiler: bool | None = None
    disabled: bool | None = None

    @field_validator("accent_color", mode="before")
    @classmethod
    def _color(cls, value: object) -> object:
        if not isinstance(value, str) or value.isdigit():
            return value
        if not COLOR.fullmatch(value):
            msg = f"accent_color {value!r} is not #RRGGBB, 0xRRGGBB or a number"
            raise ValueError(msg)
        return int(value[1:] if value.startswith("#") else value[2:], 16)


type TopLevelV2 = Annotated[
    Annotated[ActionRowV2, Tag("action_row")]
    | Annotated[SectionV2, Tag("section")]
    | Annotated[TextDisplayV2, Tag("text_display")]
    | Annotated[MediaGalleryV2, Tag("media_gallery")]
    | Annotated[SeparatorV2, Tag("separator")]
    | Annotated[FileDisplayV2, Tag("file_display")]
    | Annotated[ContainerV2, Tag("container")]
    | Annotated[ModelRefV2, Tag("model")],
    Discriminator(component_type),
]
