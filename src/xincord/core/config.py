"""Load and validate YAML configuration files."""

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from pathlib import Path


class ConfigError(Exception):
    """A configuration file could not be loaded; the message lists every problem."""


class Model(BaseModel):
    """Base class for configuration schemas: frozen, and keeping unknown keys for warnings."""

    model_config = ConfigDict(extra="allow", frozen=True)


def load_config[M: Model](path: Path, model: type[M], default: str) -> M:
    """Load ``path`` as ``model``, writing ``default`` there first if the file is missing.

    Args:
        path: The YAML file to load.
        model: The schema to validate against.
        default: The text written to ``path`` when it does not exist.

    Returns:
        The validated configuration.

    Raises:
        ConfigError: The file is not valid YAML, not a mapping, or does not match the schema.
    """
    raise NotImplementedError
