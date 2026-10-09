"""Component and modal IDs: a versioned format and the permanent v3 decoder.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/util/ComponentIdManager.kt:13-247
"""

import re
import string
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import quote, unquote

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    import discord

VERSION = 1
MAX_LENGTH = 100  # Discord's limit for component and modal IDs
LETTERS = string.ascii_lowercase
NAMESPACE = re.compile(r"[a-z0-9_-]+")
HEX = re.compile(r"-?[0-9a-f]+")


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
        hex_fields = frozenset(legacy_hex)
        if not NAMESPACE.fullmatch(namespace):
            msg = f"namespace {namespace!r} must match [a-z0-9_-]+"
            raise ComponentIdError(msg)
        if not fields or len(set(fields)) != len(fields) or len(fields) > len(LETTERS):
            msg = f"{namespace}: needs 1 to {len(LETTERS)} distinct fields"
            raise ComponentIdError(msg)
        if unknown := hex_fields - set(fields):
            msg = f"{namespace}: hex fields {sorted(unknown)} are not fields"
            raise ComponentIdError(msg)
        self._head = f"{namespace}:{VERSION}:"
        self._legacy = legacy_prefix
        self._hex = hex_fields
        self._letters = dict(zip(fields, LETTERS, strict=False))
        self._names = dict(zip(LETTERS, fields, strict=False))

    def build(self, values: Mapping[str, str | int]) -> str:
        """Return the new-format ID for ``values``; usable as a template ID builder.

        Raises:
            ComponentIdError: A field is unknown or the ID is longer than 100 characters.
        """
        pairs: list[str] = []
        for name, value in values.items():
            if name not in self._letters:
                msg = f"{self._head} has no field {name!r}"
                raise ComponentIdError(msg)
            pairs.append(f"{self._letters[name]}={quote(str(value), safe='')}")
        custom_id = self._head + ";".join(pairs)
        if len(custom_id) > MAX_LENGTH:
            msg = f"{custom_id!r} is longer than {MAX_LENGTH} characters"
            raise ComponentIdError(msg)
        return custom_id

    def parse(self, custom_id: str) -> ParsedId:
        """Return the fields of one of this codec's IDs, in either format.

        Raises:
            ComponentIdError: The ID is not this codec's, or it is malformed.
        """
        if custom_id.startswith(self._head):
            body, separator, legacy = custom_id.removeprefix(self._head), "=", False
        elif self._legacy is not None and custom_id.startswith(self._legacy):
            body, separator, legacy = custom_id.removeprefix(self._legacy), ":", True
        else:
            msg = f"{custom_id!r} is not a {self._head} ID"
            raise ComponentIdError(msg)
        fields: dict[str, str] = {}
        for segment in body.split(";") if body else ():
            # New values are escaped and v3 values could not contain the separator, so a valid
            # segment splits in exactly two.
            parts = segment.split(separator)
            if len(parts) != 2 or parts[0] not in self._names:  # noqa: PLR2004 - key and value
                msg = f"{custom_id!r}: malformed segment {segment!r}"
                raise ComponentIdError(msg)
            name = self._names[parts[0]]
            fields[name] = self._legacy_value(name, parts[1]) if legacy else _unescape(parts[1])
        return ParsedId(fields, legacy=legacy)

    def owns(self, custom_id: str) -> bool:
        """Whether ``custom_id`` starts like one of this codec's IDs, in either format."""
        return custom_id.startswith(self._head) or (
            self._legacy is not None and custom_id.startswith(self._legacy)
        )

    def upgrade(self, custom_id: str) -> str:
        """Return the new-format equivalent of one of this codec's IDs.

        Raises:
            ComponentIdError: The ID is not this codec's, or it cannot be converted.
        """
        raise NotImplementedError

    def _legacy_value(self, name: str, value: str) -> str:
        """Decode a v3 value; v3 wrote ``Int`` and ``Long`` fields in lowercase hex."""
        if name not in self._hex:
            return value
        if not HEX.fullmatch(value):
            msg = f"{name} value {value!r} is not lowercase hex"
            raise ComponentIdError(msg)
        return str(int(value, 16))


def _unescape(value: str) -> str:
    try:
        return unquote(value, errors="strict")
    except UnicodeDecodeError as error:
        msg = f"value {value!r} is not percent-encoded UTF-8"
        raise ComponentIdError(msg) from error


def upgrade_view(
    view: discord.ui.View | discord.ui.LayoutView, codecs: Iterable[ComponentIds]
) -> bool:
    """Give the buttons and selects of ``view`` new-format IDs where a codec owns a legacy one.

    ``view`` is a fresh copy, rebuilt from a message with ``from_message``; edit the message with
    it when this returns True.
    """
    raise NotImplementedError
