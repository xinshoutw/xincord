"""The plugin's component and modal IDs, which read legacy ones too."""

from xincord.core.component_ids import ComponentIds

# The fields in their order, the user ID in hex as legacy IDs hold it, and the legacy prefix, so
# that legacy panels and ticket channels keep working.
IDS = ComponentIds(
    "ticket",
    ("action", "sub_action", "color_index", "user_id", "msg_id", "btn_index"),
    legacy_prefix="ticket@",
    legacy_hex=("user_id",),
)
