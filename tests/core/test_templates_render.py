"""Message rendering: text, URLs, empty embeds, colors, timestamps and fields."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from xincord.core.templates import EmbedField, TemplateError, load_message, render_message

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.templates import Message


VALUES = {
    "user_name": "Alice",
    "dash": "-",
    "picture": "https://example.com/a.png",
    "color": "#ff0000",
}
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
# A left-to-right mark, which stands for an empty field text.
EMPTY_FIELD = chr(0x200E)


def render(tmp_path: Path, text: str, values: dict[str, str] = VALUES) -> Message:
    path = tmp_path / "template.yml"
    path.write_text(text, encoding="utf-8")
    return render_message(load_message(path), values, now=NOW)


def test_content_and_embed_text(tmp_path: Path) -> None:
    """Requirement: Message text is rendered with placeholders."""

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


def test_placeholder_without_icon(tmp_path: Path) -> None:
    """Requirement: URL fields need an http result."""

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


@pytest.mark.parametrize(
    "embed",
    ['{color_code: "#ffffff"}', '{image_url: "%dash%"}', '{description: ""}'],
)
def test_empty_embeds_are_dropped(tmp_path: Path, embed: str) -> None:
    """Requirement: Empty embeds are dropped."""

    assert render(tmp_path, f"embeds:\n  - {embed}\n").embeds == ()


def test_color_and_epoch_timestamp(tmp_path: Path) -> None:
    """Requirement: Colors and timestamps are parsed."""

    message = render(
        tmp_path,
        'embeds:\n  - {description: x, color_code: "0x9bd9d5", timestamp: "1723675788491"}\n',
    )

    (embed,) = message.embeds
    assert embed.colour is not None
    assert embed.colour.value == 0x9BD9D5
    assert embed.timestamp == datetime(2024, 8, 14, 22, 49, 48, 491000, tzinfo=UTC)


def test_now_and_placeholder_color(tmp_path: Path) -> None:
    """Requirement: Colors and timestamps are parsed."""

    message = render(
        tmp_path,
        'embeds:\n  - {description: x, color_code: "%color%", timestamp: "%now%"}\n',
    )

    (embed,) = message.embeds
    assert embed.colour is not None
    assert embed.colour.value == 0xFF0000
    assert embed.timestamp == NOW


def test_invalid_rendered_color_fails(tmp_path: Path) -> None:
    """Requirement: Colors and timestamps are parsed."""

    with pytest.raises(TemplateError, match="color"):
        render(tmp_path, 'embeds:\n  - {description: x, color_code: "%dash%"}\n')


def test_image_url_is_set(tmp_path: Path) -> None:
    """Requirement: URL fields need an http result."""

    (embed,) = render(tmp_path, 'embeds:\n  - {image_url: "%picture%"}\n').embeds

    assert embed.image.url == "https://example.com/a.png"


def test_empty_field_text(tmp_path: Path) -> None:
    """Requirement: Embed fields are trimmed and never empty."""

    message = render(
        tmp_path,
        'embeds:\n  - fields: [{name: "%dash%", value: "%empty%"}, {name: "", value: " \\t"}]\n',
        VALUES | {"empty": ""},
    )

    (embed,) = message.embeds
    assert [(field.name, field.value) for field in embed.fields] == [
        ("-", EMPTY_FIELD),
        (EMPTY_FIELD, EMPTY_FIELD),
    ]


def test_padded_field_text(tmp_path: Path) -> None:
    """Requirement: Embed fields are trimmed and never empty."""

    message = render(tmp_path, 'embeds:\n  - fields: [{name: " name ", value: "value\\n\\n"}]\n')

    (embed,) = message.embeds
    assert [(field.name, field.value) for field in embed.fields] == [("name", "value")]


def test_field_trim(tmp_path: Path) -> None:
    """Requirement: Embed fields are trimmed and never empty."""
    # The trim removes the characters up to U+0020 only: control characters go, while
    # a no-break space and an ideographic space stay.
    kept = chr(0xA0) + "x" + chr(0x3000)

    message = render(
        tmp_path,
        'embeds:\n  - fields: [{name: "%padded%", value: "%kept%"}]\n',
        VALUES | {"padded": chr(1) + "\n name\r" + chr(0x1F), "kept": kept},
    )

    (embed,) = message.embeds
    assert [(field.name, field.value) for field in embed.fields] == [("name", kept)]


def test_model_fields_trimmed(tmp_path: Path) -> None:
    """Requirement: Embed fields are trimmed and never empty."""
    path = tmp_path / "template.yml"
    path.write_text('embeds:\n  - fields: [{model_key: "f"}]\n', encoding="utf-8")

    message = render_message(load_message(path), VALUES, models={"f": EmbedField(" n ", "")})

    (embed,) = message.embeds
    assert [(field.name, field.value) for field in embed.fields] == [("n", EMPTY_FIELD)]
