"""Shared pieces of the template schemas and renderers."""

from typing import TYPE_CHECKING

import discord
from pydantic import ConfigDict

from xincord.core.config import Model
from xincord.core.placeholders import CHANNEL_TYPES, render

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from xincord.core.templates.schema import OptionSpec

ENTITY_TARGETS = ("USER", "ROLE", "CHANNEL")
# JDA channel type names that discord.py can put in a channel select.
CHANNEL_TYPE_BY_NAME = {
    name: discord.ChannelType(value)
    for value, name in CHANNEL_TYPES.items()
    if value in {kind.value for kind in discord.ChannelType}
}

type IdBuilder = Callable[[Mapping[str, str]], str]
type Item = discord.ui.Item[discord.ui.View]


class TemplateError(Exception):
    """A template is malformed or cannot be rendered; the message names the file or key."""


class TemplateModel(Model):
    """Base of the template schemas: numbers in text fields stay text, as in v3's KAML."""

    model_config = ConfigDict(extra="allow", frozen=True, coerce_numbers_to_str=True)


def require(model: TemplateModel, *names: str) -> None:
    """Fail unless every field in ``names`` is set, or the model is replaced by a ``model_key``."""
    if getattr(model, "model_key", None) is not None:
        return
    if missing := [name for name in names if getattr(model, name) is None]:
        msg = f"needs {', '.join(missing)} unless model_key is set"
        raise ValueError(msg)


def lookup(models: Mapping[str, object] | None, key: str) -> object:
    """Return the model supplied under ``key``."""
    # ponytail: model keys are looked up verbatim, as v3 did, even when they contain %...%.
    if models is None or key not in models:
        msg = f"no model named {key!r} was supplied"
        raise TemplateError(msg)
    return models[key]


def resolve_model[T](models: Mapping[str, object] | None, key: str, kind: type[T]) -> T:
    """Return the model under ``key``, checking that it is a ``kind``."""
    model = lookup(models, key)
    if not isinstance(model, kind):
        msg = f"model {key!r} is a {type(model).__name__}, expected {kind.__name__}"
        raise TemplateError(msg)
    return model


def custom_id(
    uid: Mapping[str, str] | None,
    values: Mapping[str, str],
    build_id: IdBuilder | None,
) -> str:
    """Build a component ID from a ``uid`` map with placeholders applied."""
    if build_id is None:
        msg = "components with a uid need an ID builder"
        raise TemplateError(msg)
    return build_id({key: render(value, values) for key, value in (uid or {}).items()})


def optional_text(text: str | None, values: Mapping[str, str]) -> str | None:
    """Render ``text`` unless it is None."""
    return None if text is None else render(text, values)


def resolve_emoji(
    model_key: str | None,
    formatted: str | None,
    values: Mapping[str, str],
    models: Mapping[str, object] | None,
) -> discord.PartialEmoji | str | None:
    """Return the emoji model under ``model_key``, or parse ``formatted``."""
    if model_key is not None:
        model = lookup(models, model_key)
        if not isinstance(model, discord.PartialEmoji | str):
            msg = f"model {model_key!r} is a {type(model).__name__}, expected an emoji"
            raise TemplateError(msg)
        return model
    return None if formatted is None else discord.PartialEmoji.from_str(render(formatted, values))


def select_option(
    spec: OptionSpec,
    values: Mapping[str, str],
    models: Mapping[str, object] | None,
) -> discord.SelectOption:
    """Render a string select option, or return its model."""
    if spec.model_key is not None:
        return resolve_model(models, spec.model_key, discord.SelectOption)
    emoji = (
        resolve_emoji(spec.emoji.model_key, spec.emoji.name, values, models) if spec.emoji else None
    )
    return discord.SelectOption(
        label=render(spec.label or "", values),
        value=render(spec.value or "", values),
        description=optional_text(spec.description, values),
        emoji=emoji,
        default=spec.default,
    )
