"""The builder's modals: v3's six modals, pre-filled with the draft as written."""

from typing import TYPE_CHECKING, Any, cast

import discord
import pytest

from plugin_fakes import golden
from xincord.plugins.giveaway.model import Draft, Prize

if TYPE_CHECKING:
    from conftest import Scene
    from discord_fakes import FakeInteraction

GOLDEN = golden("giveaway")
TAIPEI = 'timeZone: "Asia/Taipei"\n'

type Input = tuple[str, str | None, discord.ui.TextInput[discord.ui.Modal]]


def opened(interaction: FakeInteraction) -> discord.ui.Modal:
    """The modal that the press opened, its only response."""
    [(method, fields)] = interaction.sent
    assert method == "response.send_modal"
    return cast("discord.ui.Modal", fields["modal"])


def inputs(modal: discord.ui.Modal) -> list[Input]:
    """Each text input's ID, its label and the input, in order."""
    found: list[Input] = []
    for item in modal.children:
        assert isinstance(item, discord.ui.Label)
        text_input = cast("discord.ui.TextInput[discord.ui.Modal]", item.component)
        found.append((str(text_input.custom_id), item.text, text_input))
    return found


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
@pytest.mark.parametrize("name", list(GOLDEN["modals"]))
async def test_modals(scene: Scene, name: str, locale: str) -> None:
    """Requirement: Builder buttons open pre-filled modals."""
    expected: dict[str, Any] = GOLDEN["modals"][name]
    scene.keep(Draft())

    modal = opened(await scene.press(name, scene.who(locale=locale)))

    assert modal.custom_id == f"giveaway:1:a=create;b={name}"
    assert modal.title == expected[locale]["title"]
    found = inputs(modal)
    assert [label for _, label, _ in found] == expected[locale]["labels"]
    assert [text_input.placeholder for _, _, text_input in found] == expected[locale][
        "placeholders"
    ]
    shapes = [
        [custom_id, text_input.style.name, text_input.max_length, text_input.required]
        for custom_id, _, text_input in found
    ]
    assert shapes == expected["inputs"]
    assert all(text_input.min_length is None for _, _, text_input in found)  # v3 set none


async def test_title_modal(scene: Scene) -> None:
    """Requirement: Builder buttons open pre-filled modals."""
    scene.keep(Draft(title="Nitro"))

    [(_, _, title)] = inputs(opened(await scene.press("set-title")))

    assert title.default == "Nitro"


@pytest.mark.parametrize(
    ("name", "draft", "default"),
    [
        ("set-description", Draft(description="desc"), "desc"),
        ("set-sponsor", Draft(sponsor="Shop"), "Shop"),
        ("set-thumbnail", Draft(thumbnail_url="https://x/y.png"), "https://x/y.png"),
        ("set-title", Draft(), None),  # an empty value leaves the input empty, as v3
        ("set-description", Draft(description="  "), None),
    ],
)
async def test_values(scene: Scene, name: str, draft: Draft, default: str | None) -> None:
    """Requirement: Builder buttons open pre-filled modals."""
    scene.keep(draft)

    [(_, _, text_input)] = inputs(opened(await scene.press(name)))

    assert text_input.default == default


@pytest.mark.parametrize("config", [TAIPEI])
@pytest.mark.parametrize(("end_at", "shown"), [(1772330400, "2026-03-01 10:00"), (0, None)])
async def test_end_time_modal(scene: Scene, end_at: int, shown: str | None) -> None:
    """Requirement: Builder buttons open pre-filled modals."""
    scene.keep(Draft(end_at=end_at))

    [(_, _, end_time)] = inputs(opened(await scene.press("set-end-time")))

    assert end_time.default == shown


@pytest.mark.parametrize("locale", ["en-US", "zh-TW"])
async def test_prize_modal(scene: Scene, locale: str) -> None:
    """Requirement: Builder buttons open pre-filled modals."""
    scene.keep(Draft(prizes=(Prize("Nitro", 2), Prize("Sticker", 1))))

    found = inputs(opened(await scene.press("add-prize", scene.who(locale=locale))))

    [(_, _, name), (_, _, count)] = found
    assert name.default == GOLDEN["third-prize"][locale]
    assert count.default == "1"


async def test_typed_placeholders(scene: Scene) -> None:
    """Requirement: Builder buttons open pre-filled modals."""
    scene.keep(Draft(title="%bot_name%"))

    [(_, _, title)] = inputs(opened(await scene.press("set-title")))

    assert title.default == "%bot_name%"  # v3 expanded it, and a title of %ga@title% threw


# An operator's set-title modal that shows v3's values of the press, as Placeholder.get(event) gave.
OPERATOR_MODAL = {
    "lang/en-US/modal/set-title.yaml": (
        "uid: {action: create, sub_action: set-title}\n"
        'title: "%user_name% (%user_id%), %bot_name%"\n'
        "text_inputs:\n"
        '  - {uid: title, label: "Title", style: SHORT, value: "%ga@title%"}\n'
    )
}


@pytest.mark.parametrize("files", [OPERATOR_MODAL])
async def test_interaction_values(scene: Scene) -> None:
    """Requirement: Builder buttons open pre-filled modals."""
    scene.keep(Draft(title="Nitro"))

    modal = opened(await scene.press("set-title"))

    assert modal.title == "alice (7), xincord"
    [(_, _, title)] = inputs(modal)
    assert title.default == "Nitro"
