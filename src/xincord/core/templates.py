"""Message and modal templates: YAML loading, validation and rendering to discord.py objects."""

import re
from typing import TYPE_CHECKING, Annotated, Literal, Self

import yaml
from pydantic import ConfigDict, Field, model_validator

from xincord.core.config import Model, parse_model
from xincord.core.placeholders import CHANNEL_TYPES

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from xincord.core.i18n import Lang

COLOR = re.compile(r"(?:#|0[xX])[0-9a-fA-F]{1,6}")
ENTITY_TARGETS = ("USER", "ROLE", "CHANNEL")
JDA_CHANNEL_TYPES = frozenset(CHANNEL_TYPES.values())


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
            kind for kind in self.channel_types if kind.upper() not in JDA_CHANNEL_TYPES
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
    uid: str | None = None
    label: str | None = None
    value: str | None = None
    placeholder: str | None = None
    min_length: int = -1
    max_length: int = -1
    style: Literal["SHORT", "PARAGRAPH"] | None = None
    required: bool = True

    @model_validator(mode="after")
    def _complete(self) -> Self:
        _require(self, "uid", "label", "style")
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
