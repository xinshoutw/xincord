"""The trim of titles, links, contents and the model's text.

It removes whitespace: Python's ``str.isspace()`` without U+0085. The module imports nothing of the
plugin, so that every module can use it.
"""

NEXT_LINE = "\x85"  # Python's isspace() takes it; the trim leaves it


def _whitespace(character: str) -> bool:
    """Whitespace for the trim."""
    return character.isspace() and character != NEXT_LINE


def trim(text: str) -> str:
    """``text`` without the leading and trailing whitespace characters (U+0085 aside)."""
    start, end = 0, len(text)
    while start < end and _whitespace(text[start]):
        start += 1
    while end > start and _whitespace(text[end - 1]):
        end -= 1
    return text[start:end]
