"""Load and validate YAML configuration files."""

import logging
from enum import StrEnum
from importlib.resources import files
from typing import TYPE_CHECKING, Literal, Self, cast

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    PositiveFloat,
    PositiveInt,
    ValidationError,
    model_validator,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """A configuration file could not be loaded; the message lists every problem."""


class Model(BaseModel):
    """Base class for configuration schemas: frozen, and keeping unknown keys for warnings."""

    model_config = ConfigDict(extra="allow", frozen=True)


def load_config[M: Model](path: Path, model: type[M], default: str) -> M:
    """Load ``path`` as ``model``, writing ``default`` there first if the file is missing.

    Unknown keys are logged as warnings and otherwise ignored.

    Args:
        path: The YAML file to load.
        model: The schema to validate against.
        default: The text written to ``path`` when it does not exist.

    Returns:
        The validated configuration.

    Raises:
        ConfigError: The file cannot be read, is not valid YAML, is not a mapping, or does not
            match the schema.
    """
    try:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(default, encoding="utf-8")
            logger.info("Created %s from the default", path)
        data: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        msg = f"{path}: {error}"
        raise ConfigError(msg) from error
    except yaml.YAMLError as error:
        msg = f"{path}: invalid YAML: {error}"
        raise ConfigError(msg) from error

    if data is None:
        data = {}
    if not isinstance(data, dict):
        msg = f"{path}: expected a mapping at the top level"
        raise ConfigError(msg)
    try:
        config = model.model_validate(data)
    except ValidationError as error:
        lines = [f"{path}: {_dotted(issue['loc'])}: {issue['msg']}" for issue in error.errors()]
        raise ConfigError("\n".join(lines)) from error

    for key in _unknown_keys(config, ""):
        logger.warning("%s: unknown key %s", path, key)
    return config


def _dotted(location: tuple[int | str, ...]) -> str:
    return ".".join(str(part) for part in location) or "<root>"


def _unknown_keys(value: object, prefix: str) -> Iterator[str]:
    if isinstance(value, BaseModel):
        for key in value.model_extra or {}:
            yield prefix + key
        for name in type(value).model_fields:
            yield from _unknown_keys(getattr(value, name), f"{prefix}{name}.")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(cast("Sequence[object]", value)):
            yield from _unknown_keys(item, f"{prefix}{index}.")


class ActivityType(StrEnum):
    """Kinds of bot activity."""

    PLAYING = "playing"
    STREAMING = "streaming"
    LISTENING = "listening"
    WATCHING = "watching"
    CUSTOM = "custom"
    COMPETING = "competing"


class Activity(Model):
    """One entry of the rotating bot activity."""

    type: ActivityType
    text: str
    seconds: PositiveFloat = 5
    url: str | None = None

    @model_validator(mode="after")
    def _streaming_has_url(self) -> Self:
        if self.type is ActivityType.STREAMING and not self.url:
            msg = "a streaming activity needs a url"
            raise ValueError(msg)
        return self


class Status(Model):
    """The rotating bot activity."""

    activities: tuple[Activity, ...] = ()


class InteractionLogTarget(Model):
    """A channel that receives a line for each matching interaction."""

    guild_id: PositiveInt
    channel_id: PositiveInt
    types: tuple[Literal["command", "button", "modal"], ...]
    format: str = "[%cl_type%] %user_name% `%cl_interaction_string%`"


class CoreConfig(Model):
    """The core ``config.yaml``."""

    token: str = ""
    status: Status = Status()
    interaction_log: tuple[InteractionLogTarget, ...] = ()


def default_core_config() -> str:
    """Return the text of the default core ``config.yaml``."""
    return files(__package__).joinpath("resources/config.yaml").read_text(encoding="utf-8")
