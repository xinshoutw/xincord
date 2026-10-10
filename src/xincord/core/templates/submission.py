"""Reading a modal submission back: the values of its text inputs."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


def modal_values(data: Mapping[str, object] | None) -> dict[str, str]:
    """Return the value of each text input in a modal submission, by its custom ID.

    Args:
        data: ``interaction.data`` of a ``modal_submit`` interaction.
    """
    raise NotImplementedError
