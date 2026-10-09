"""Message rendering: text, URLs, empty embeds, colors and timestamps.

Kotlin:
    XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/builtin/messagecreator/v1/builder/MessageBuilder.kt:28-157
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from xincord.core.templates import TemplateError, load_message, render_message

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.templates import Message


def xfail(requirement: str) -> pytest.MarkDecorator:
    return pytest.mark.xfail(strict=True, raises=NotImplementedError, reason=requirement)


TEXT = xfail("Message text is rendered with placeholders")
URLS = xfail("URL fields need an http result")
EMPTY = xfail("Empty embeds are dropped")
FORMATS = xfail("Colors and timestamps follow v3")

VALUES = {
    "user_name": "Alice",
    "dash": "-",
    "picture": "https://example.com/a.png",
    "color": "#ff0000",
}
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


def render(tmp_path: Path, text: str, values: dict[str, str] = VALUES) -> Message:
    path = tmp_path / "template.yml"
    path.write_text(text, encoding="utf-8")
    return render_message(load_message(path), values, now=NOW)


@TEXT
def test_content_and_embed_text(tmp_path: Path) -> None:
    message = render(
        tmp_path,
        """\
content: "Hi %user_name%"
embeds:
  - author: {name: "A %user_name%"}
    title: {text: "T %user_name%"}
    description: "D %user_name%"
    fields: [{name: "N %user_name%", value: "V %user_name%", inline: true}]
    footer: {text: "F %user_name%"}
""",
    )

    (embed,) = message.embeds
    assert message.content == "Hi Alice"
    assert (embed.author.name, embed.title, embed.description) == ("A Alice", "T Alice", "D Alice")
    field = embed.fields[0]
    assert (field.name, field.value, field.inline) == ("N Alice", "V Alice", True)
    assert embed.footer.text == "F Alice"
    assert message.view is None


@URLS
def test_placeholder_without_icon(tmp_path: Path) -> None:
    message = render(
        tmp_path,
        """\
embeds:
  - author: {name: "a", url: "ftp://example.com", icon_url: "%dash%"}
    title: {text: "t", url: "http://example.com"}
    thumbnail_url: "%picture%"
    image_url: "%dash%"
    footer: {text: "f", icon_url: "https://example.com/f.png"}
""",
    )

    (embed,) = message.embeds
    assert (embed.author.url, embed.author.icon_url) == (None, None)
    assert embed.url == "http://example.com"
    assert embed.thumbnail.url == "https://example.com/a.png"
    assert embed.image.url is None
    assert embed.footer.icon_url == "https://example.com/f.png"


@EMPTY
@pytest.mark.parametrize(
    "embed",
    ['{color_code: "#ffffff"}', '{image_url: "%dash%"}', '{description: ""}'],
)
def test_empty_embeds_are_dropped(tmp_path: Path, embed: str) -> None:
    assert render(tmp_path, f"embeds:\n  - {embed}\n").embeds == ()


@FORMATS
def test_color_and_epoch_timestamp(tmp_path: Path) -> None:
    message = render(
        tmp_path,
        'embeds:\n  - {description: x, color_code: "0x9bd9d5", timestamp: "1723675788491"}\n',
    )

    (embed,) = message.embeds
    assert embed.colour is not None
    assert embed.colour.value == 0x9BD9D5
    assert embed.timestamp == datetime(2024, 8, 14, 22, 49, 48, 491000, tzinfo=UTC)


@FORMATS
def test_now_and_placeholder_color(tmp_path: Path) -> None:
    message = render(
        tmp_path,
        'embeds:\n  - {description: x, color_code: "%color%", timestamp: "%now%"}\n',
    )

    (embed,) = message.embeds
    assert embed.colour is not None
    assert embed.colour.value == 0xFF0000
    assert embed.timestamp == NOW


@FORMATS
def test_invalid_rendered_color_fails(tmp_path: Path) -> None:
    with pytest.raises(TemplateError, match="color"):
        render(tmp_path, 'embeds:\n  - {description: x, color_code: "%dash%"}\n')
