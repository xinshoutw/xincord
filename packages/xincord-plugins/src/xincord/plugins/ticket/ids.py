"""The plugin's component and modal IDs, which read v3's too."""

from xincord.core.component_ids import ComponentIds

# v3's fields in v3's order, the user ID in hex as v3 wrote it, and v3's prefix, so that v3's
# panels and ticket channels keep working.
IDS = ComponentIds(
    "ticket",
    ("action", "sub_action", "color_index", "user_id", "msg_id", "btn_index"),
    legacy_prefix="ticket@",
    legacy_hex=("user_id",),
)
