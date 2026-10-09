# Owner review queue

Changes pushed while the owner was away, for review afterwards. Each plugin port adds one section
with what the owner has not seen yet:

- **User-visible changes:** copy, commands, options, permissions and interaction flows that differ
  from v3 or are new.
- **Choices made without the owner:** questions the inventory and `decisions.md` did not settle,
  the option implemented, and the alternative.
- **Manual checks:** what needs a real guild, a token or Docker (the smoke checklist lives in the
  archived change's `design.md`).

When the owner answers an item, record the answer in `HANDOFF.md` section 6 and delete the item
here; delete a section once it is empty.
