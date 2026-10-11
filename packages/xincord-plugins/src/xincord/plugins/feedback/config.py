"""The plugin's ``config.yaml``."""

from typing import Annotated

from pydantic import StringConstraints

from xincord.core.config import Model

# Discord's limit for a message's content.
REPLY_MAX = 2000

# A reply sent as written. Discord refuses an empty or blank message and one over 2000 characters,
# so such a reply disables the plugin at load with an error that names the key.
Reply = Annotated[str, StringConstraints(pattern=r"\S", max_length=REPLY_MAX)]


class Config(Model):
    """``plugins/Feedback/config.yaml``: the plugin's replies, sent as written.

    The core config's ``plugins`` list enables the plugin; an ``enabled`` key here only warns. The
    first three replies are required; the two failure replies have English defaults. The bundled
    file holds zh-TW texts.
    """

    form_no_permission: Reply  # to a user without Administrator who runs the command
    form_not_you: Reply  # to anyone but the rated member who presses a star
    form_success: Reply  # to the administrator once the form is posted
    form_failure: Reply = "Failed to create the form"  # when the form cannot be posted
    # To the member when the feedback cannot be posted to the submit channel.
    form_submit_failure: Reply = "Failed to submit the feedback"
