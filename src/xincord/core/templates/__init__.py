"""Message and modal templates: YAML loading, validation and rendering to discord.py objects."""

from typing import TYPE_CHECKING, Self

from xincord.core.templates.base import IdBuilder, TemplateError
from xincord.core.templates.render import EmbedField, Message, render_message, render_modal
from xincord.core.templates.schema import (
    MessageTemplate,
    ModalTemplate,
    load_message,
    load_modal,
)

if TYPE_CHECKING:
    from pathlib import Path

    from xincord.core.i18n import Lang

__all__ = [
    "EmbedField",
    "IdBuilder",
    "Message",
    "MessageTemplate",
    "ModalTemplate",
    "TemplateError",
    "Templates",
    "load_message",
    "load_modal",
    "render_message",
    "render_modal",
]


class Templates:
    """Every message and modal template of one plugin, parsed when the plugin loads."""

    def __init__(
        self,
        lang: Lang,
        messages: dict[Path, MessageTemplate],
        modals: dict[Path, ModalTemplate],
    ) -> None:
        """Wrap parsed templates; use :meth:`load` instead."""
        self._lang = lang
        self._messages = messages
        self._modals = modals

    @classmethod
    def load(cls, lang: Lang) -> Self:
        """Load every template of every locale in ``lang``.

        Raises:
            TemplateError: A template is malformed.
        """
        messages: dict[Path, MessageTemplate] = {}
        modals: dict[Path, ModalTemplate] = {}
        for table in lang.templates.values():
            for name, path in table.items():
                if name.startswith("message/"):
                    messages[path] = load_message(path)
                else:
                    modals[path] = load_modal(path)
        return cls(lang, messages, modals)

    def message(self, name: str, locale: str) -> MessageTemplate:
        """Return message template ``name`` in ``locale``, else in the default locale."""
        return self._messages[self._lang.template(f"message/{name}", locale)]

    def modal(self, name: str, locale: str) -> ModalTemplate:
        """Return modal template ``name`` in ``locale``, else in the default locale."""
        return self._modals[self._lang.template(f"modal/{name}", locale)]
