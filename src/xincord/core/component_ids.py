"""Component and modal IDs: a versioned format and the permanent v3 decoder.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/util/ComponentIdManager.kt:13-247
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence


class ComponentIdError(ValueError):
    """An ID cannot be built, or is not a valid ID of the codec that parses it."""


@dataclass(frozen=True)
class ParsedId:
    """The fields of a parsed ID, and whether it used the v3 format."""

    fields: Mapping[str, str]
    legacy: bool


class ComponentIds:
    """Builds and parses the IDs of one plugin."""

    def __init__(
        self,
        namespace: str,
        fields: Sequence[str],
        *,
        legacy_prefix: str | None = None,
        legacy_hex: Iterable[str] = (),
    ) -> None:
        """Create a codec.

        Args:
            namespace: Names the plugin at the start of every new ID (``[a-z0-9_-]+``).
            fields: Field names; their positions give the letters. Start with the plugin's v3
                fields in v3 order and only ever append.
            legacy_prefix: The plugin's v3 prefix, such as ``ticket@``, if it had one.
            legacy_hex: Fields that v3 wrote in hexadecimal.

        Raises:
            ComponentIdError: The namespace or the field list is invalid.
        """
        raise NotImplementedError

    def build(self, values: Mapping[str, str | int]) -> str:
        """Return the new-format ID for ``values``; usable as a template ID builder.

        Raises:
            ComponentIdError: A field is unknown or the ID is longer than 100 characters.
        """
        raise NotImplementedError

    def parse(self, custom_id: str) -> ParsedId:
        """Return the fields of one of this codec's IDs, in either format.

        Raises:
            ComponentIdError: The ID is not this codec's, or it is malformed.
        """
        raise NotImplementedError

    def owns(self, custom_id: str) -> bool:
        """Whether ``custom_id`` starts like one of this codec's IDs, in either format."""
        raise NotImplementedError
