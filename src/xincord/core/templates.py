"""Message and modal templates: YAML loading, validation and rendering to discord.py objects."""

from typing import TYPE_CHECKING, Self

from xincord.core.config import Model

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.i18n import Lang


class TemplateError(Exception):
    """A template is malformed or cannot be rendered; the message names the file or key."""


class MessageTemplate(Model):
    """A parsed message template."""


class ModalTemplate(Model):
    """A parsed modal template."""


def load_message(path: Path) -> MessageTemplate:
    """Parse and validate a message template, warning about unknown keys.

    Raises:
        TemplateError: The file is not valid YAML or not a valid template.
    """
    raise NotImplementedError


def load_modal(path: Path) -> ModalTemplate:
    """Parse and validate a modal template, warning about unknown keys.

    Raises:
        TemplateError: The file is not valid YAML or not a valid template.
    """
    raise NotImplementedError


class Templates:
    """Every message and modal template of one plugin, parsed when the plugin loads."""

    @classmethod
    def load(cls, lang: Lang) -> Self:
        """Load every template of every locale in ``lang``.

        Raises:
            TemplateError: A template is malformed.
        """
        raise NotImplementedError

    def message(self, name: str, locale: str) -> MessageTemplate:
        """Return message template ``name`` in ``locale``, else in the default locale."""
        raise NotImplementedError

    def modal(self, name: str, locale: str) -> ModalTemplate:
        """Return modal template ``name`` in ``locale``, else in the default locale."""
        raise NotImplementedError
