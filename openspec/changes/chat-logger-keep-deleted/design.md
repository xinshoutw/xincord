## Context

The cog takes a deleted message out of its message file with `Messages.pop` (alone) or
`Messages.pop_all` (bulk deletion) and logs what it took; `_take` reads each row and deletes it in
one transaction per file. v3 logged the deletion and kept the row. Kept rows still expire with the
retention (`retention_days`, 5 years by default) and leave with the guild under `log_all: false`.

## Goals / Non-Goals

**Goals:** a config switch between removing (default) and keeping a deleted message's text.

**Non-Goals:** marking kept rows as deleted (v3 did not; the log channel already holds the
deletion); a separate retention for deleted texts; a command to read them.

## Decisions

### One flag on the existing reads

`pop` and `pop_all` take `keep`, and `_take` deletes the rows only without it, so both deletion
paths read the rows the same way. The cog passes `config.keep_deleted`. Alternative: separate
`get` methods, which would duplicate the per-file lookup.

### The key's name and default

`keep_deleted: false`, a boolean beside `log_all`, read at load like the other keys, so a reload
applies a change. Alternative: `delete_deleted_texts: true`, a negative name for the default.

## Manual check

With `keep_deleted: true` in the test guild's `plugins/ChatLogger/config.yaml` and a reload:
delete a message in a logged channel; the listen channel gets the deletion, and the message is
still in `data/ChatLogger/messages-*.db`. With the key back to false, the next deletion removes it.
