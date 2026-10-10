"""Reading a modal submission back: the values of its text inputs."""

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

# Discord's component types in a modal submission.
ACTION_ROW = 1
TEXT_INPUT = 4
LABEL = 18


def modal_values(data: Mapping[str, object] | None) -> dict[str, str]:
    """Return the value of each text input in a modal submission, by its custom ID.

    Inputs sit in labels, as :func:`render_modal` sends them, or in the action rows of older
    modals; other components, such as text displays and selects, are skipped. discord.py reads
    submissions only for the modals it dispatches, and the core stops its modals.

    Args:
        data: ``interaction.data`` of a ``modal_submit`` interaction.
    """
    components = _components(_mappings((data or {}).get("components")))
    return {
        str(component.get("custom_id")): str(component.get("value", ""))
        for component in components
        if component.get("type") == TEXT_INPUT
    }


def _components(found: list[Mapping[str, object]]) -> Iterator[Mapping[str, object]]:
    """Yield the components in ``found`` and, after each label or action row, its children."""
    for component in found:
        yield component
        kind = component.get("type")
        if kind == LABEL:
            yield from _components(_mappings([component.get("component")]))
        elif kind == ACTION_ROW:
            yield from _components(_mappings(component.get("components")))


def _mappings(value: object) -> list[Mapping[str, object]]:
    """The dictionaries in ``value``, or none if it is not a list."""
    items = cast("list[object]", value) if isinstance(value, list) else []
    return [cast("Mapping[str, object]", item) for item in items if isinstance(item, dict)]
