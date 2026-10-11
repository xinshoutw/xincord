"""A message's text as the plugin stores it, and the texts that fit an embed field."""

import discord

from xincord.plugins.chat_logger.text import fit, message_text


def rich(**fields: object) -> discord.Embed:
    """A rich embed, as Discord sends a bot's or a webhook's embed, from its payload."""
    return discord.Embed.from_dict({"type": "rich", **fields})


def test_plain_message() -> None:
    """Requirement: A message's text is its content and its rich embeds."""
    assert message_text("hello", []) == "hello"
    assert message_text("", []) == ""  # an attachment alone: v3 stored the empty content too


def test_content_and_embeds() -> None:
    """Requirement: A message's text is its content and its rich embeds."""
    embed = rich(
        author={"name": "A"},
        title="T",
        description="D",
        fields=[{"name": "n", "value": "v"}, {"name": "m", "value": "w"}],
    )

    # v3 left the content out when the message had embeds, and put no line between the
    # description and the first field.
    assert message_text("see", [embed]) == "see\n\nA\nT\n\nD\n\nn\nv\n\nm\nw"


def test_missing_parts() -> None:
    """Requirement: A message's text is its content and its rich embeds."""
    # v3 appended "null" for a missing title or description.
    assert message_text("", [rich(fields=[{"name": "n", "value": "v"}])]) == "n\nv"
    assert message_text("", [rich(title="T"), rich(description="D")]) == "T\n\nD"
    assert message_text("", [rich(author={"name": "A"}, description="D")]) == "A\n\nD"
    assert message_text("x", [rich(image={"url": "https://example.com/a.png"})]) == "x"


def test_link_preview() -> None:
    """Requirement: A message's text is its content and its rich embeds."""
    # Discord adds previews of the content's links after the message is sent.
    previews = [
        discord.Embed.from_dict({"type": kind, "title": "Example", "description": "A page"})
        for kind in ("link", "article", "image", "video", "gifv")
    ]

    assert message_text("https://example.com", previews) == "https://example.com"
    # An embed without a type is rich, Discord's default.
    assert message_text("", [discord.Embed.from_dict({"title": "T"})]) == "T"


def test_short_text() -> None:
    """Requirement: Logged texts are shown as written and fit an embed field."""
    assert fit("%bot_id% %cl_msg_after%") == "%bot_id% %cl_msg_after%"
    assert fit("a" * 1024) == "a" * 1024


def test_long_text() -> None:
    """Requirement: Logged texts are shown as written and fit an embed field."""
    # v3 threw for a field over 1024 characters, so the log was lost.
    assert fit("a" * 2000) == "a" * 1021 + "..."
    # Counted in UTF-16 code units, as JDA did: a character outside the BMP takes two.
    wide = chr(0x1F50A)
    assert fit(wide * 600) == wide * 510 + "..."
    assert fit("a" + wide * 600) == "a" + wide * 510 + "..."
