"""Message rendering: component rows and model keys.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/messagecreator/v1/builder/MessageBuilder.kt:159-293
"""

from typing import TYPE_CHECKING

import discord
import pytest

from xincord.core.templates import (
    EmbedField,
    Message,
    TemplateError,
    load_message,
    render_message,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


def xfail(requirement: str) -> pytest.MarkDecorator:
    return pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=requirement)


ROWS = xfail("Components keep their rows")
MODELS = xfail("Model keys insert runtime objects")
TEXT = xfail("Message text is rendered with placeholders")

VALUES = {"user_name": "Alice"}


class IdBuilder:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def __call__(self, uid: Mapping[str, str]) -> str:
        self.calls.append(dict(uid))
        return "id:" + ",".join(f"{key}={value}" for key, value in uid.items())


def render(
    tmp_path: Path,
    text: str,
    *,
    build_id: IdBuilder | None = None,
    models: Mapping[str, object] | None = None,
) -> Message:
    path = tmp_path / "template.yml"
    path.write_text(text, encoding="utf-8")
    return render_message(load_message(path), VALUES, build_id=build_id, models=models)


TWO_ROWS = """\
components:
  - !ButtonsComponent
    buttons:
      - {style: 5, url: "https://example.com", label: "Open"}
      - uid: {action: "join"}
        label: "Join"
        emoji: {formatted: "<:join:111>"}
        disabled: true
  - !EntitySelectMenu
    uid: {action: "pick"}
    select_target_type: "channel"
    channel_types: ["TEXT", "NEWS"]
"""


@ROWS
async def test_two_rows(tmp_path: Path) -> None:
    message = render(tmp_path, TWO_ROWS, build_id=IdBuilder())

    assert message.view is not None
    link, join, picker = message.view.children
    assert isinstance(link, discord.ui.Button)
    assert isinstance(join, discord.ui.Button)
    assert isinstance(picker, discord.ui.ChannelSelect)
    assert (link.style, link.url, link.row) == (discord.ButtonStyle.link, "https://example.com", 0)
    assert (join.style, join.custom_id, join.disabled) == (
        discord.ButtonStyle.primary,
        "id:action=join",
        True,
    )
    assert join.emoji == discord.PartialEmoji(name="join", id=111)
    assert join.row == 0
    assert (picker.custom_id, picker.row) == ("id:action=pick", 1)
    assert picker.channel_types == [discord.ChannelType.text, discord.ChannelType.news]
    assert message.view.is_finished()


@ROWS
async def test_string_user_and_role_selects(tmp_path: Path) -> None:
    text = """\
components:
  - !StringSelectMenu
    uid: {action: "choose"}
    placeholder: "Pick, %user_name%"
    min: 1
    max: 2
    options:
      - {label: "A", value: "a", description: "first", default: true, emoji: {name: "<:a:1>"}}
      - {label: "B", value: "b"}
  - !EntitySelectMenu {uid: {action: "user"}, select_target_type: "USER"}
  - !EntitySelectMenu {uid: {action: "role"}, select_target_type: "ROLE", max: 3}
"""

    message = render(tmp_path, text, build_id=IdBuilder())

    assert message.view is not None
    choose, user, role = message.view.children
    assert isinstance(choose, discord.ui.Select)
    assert isinstance(user, discord.ui.UserSelect)
    assert isinstance(role, discord.ui.RoleSelect)
    assert (choose.placeholder, choose.min_values, choose.max_values) == ("Pick, Alice", 1, 2)
    first = choose.options[0]
    assert (first.label, first.value, first.description, first.default) == ("A", "a", "first", True)
    assert first.emoji == discord.PartialEmoji(name="a", id=1)
    assert (user.row, role.row, role.max_values) == (1, 2, 3)


@ROWS
async def test_components_need_an_id_builder(tmp_path: Path) -> None:
    with pytest.raises(TemplateError, match="ID builder"):
        render(tmp_path, TWO_ROWS)


@ROWS
async def test_link_buttons_need_no_builder(tmp_path: Path) -> None:
    text = "components:\n  - !ButtonsComponent\n    buttons: [{style: 5, url: 'https://e.com'}]\n"

    message = render(tmp_path, text)

    assert message.view is not None
    assert len(message.view.children) == 1


@TEXT
async def test_component_text_and_uid_use_placeholders(tmp_path: Path) -> None:
    text = """\
components:
  - !ButtonsComponent
    buttons: [{uid: {who: "%user_name%", n: 7}, label: "L %user_name%", style: 4}]
"""
    build_id = IdBuilder()

    message = render(tmp_path, text, build_id=build_id)

    assert message.view is not None
    (button,) = message.view.children
    assert isinstance(button, discord.ui.Button)
    assert (button.label, button.style) == ("L Alice", discord.ButtonStyle.danger)
    assert build_id.calls == [{"who": "Alice", "n": "7"}]


@MODELS
async def test_field_and_button_models(tmp_path: Path) -> None:
    text = """\
embeds:
  - description: "x"
    fields: [{model_key: "f"}, {name: "plain", value: "v"}]
components:
  - !ButtonsComponent
    buttons: [{model_key: "b"}]
"""
    button = discord.ui.Button[discord.ui.View](label="model", custom_id="b")

    message = render(tmp_path, text, models={"f": EmbedField("n", "v", inline=True), "b": button})

    (embed,) = message.embeds
    assert [(field.name, field.inline) for field in embed.fields] == [("n", True), ("plain", False)]
    assert message.view is not None
    assert message.view.children == [button]
    assert button.row == 0


@MODELS
async def test_message_embed_row_option_and_emoji_models(tmp_path: Path) -> None:
    prebuilt = Message(content="prebuilt")
    assert render(tmp_path, "model_key: whole\n", models={"whole": prebuilt}) is prebuilt

    embed = discord.Embed(title="model")
    row = [discord.ui.Button[discord.ui.View](label="r1", custom_id="r1")]
    option = discord.SelectOption(label="o", value="o")
    emoji = discord.PartialEmoji(name="e", id=5)
    text = """\
embeds: [{model_key: "embed"}]
components:
  - !ButtonsComponent {model_key: "row"}
  - !StringSelectMenu {uid: {a: b}, options: [{model_key: "option"}]}
  - !ButtonsComponent
    buttons: [{uid: {a: c}, emoji: {model_key: "emoji"}}]
"""
    models: dict[str, object] = {"embed": embed, "row": row, "option": option, "emoji": emoji}

    message = render(tmp_path, text, build_id=IdBuilder(), models=models)

    assert message.embeds == (embed,)
    assert message.view is not None
    first, select, last = message.view.children
    assert first is row[0]
    assert isinstance(select, discord.ui.Select)
    assert select.options == [option]
    assert isinstance(last, discord.ui.Button)
    assert last.emoji == emoji


@MODELS
@pytest.mark.parametrize("models", [{}, {"board": "not an embed"}])
async def test_missing_or_wrong_model(tmp_path: Path, models: dict[str, object]) -> None:
    with pytest.raises(TemplateError, match="board"):
        render(tmp_path, "embeds: [{model_key: board}]\n", models=models)
