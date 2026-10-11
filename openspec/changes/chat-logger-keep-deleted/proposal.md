## Why

`port-chat-logger` removes a deleted message's text from the store once its deletion is handled,
where v3 kept it. On 2026-10-11 the owner kept that default and asked for a config setting that
keeps the texts instead, for operators who want them, for instance as evidence after a deletion.

## What Changes

- New `config.yaml` key `keep_deleted`, false by default: with it true, a deleted message, alone or
  in a bulk deletion, stays stored after its deletion is logged, until `retention_days` removes it,
  as v3 kept it. With it false or missing, nothing changes.
- The bundled `config.yaml` lists the key with a comment (new copy); existing operator files keep
  their text and run with the default.
- A value that is not a boolean stops the plugin from loading, with the key named.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `plugin-chat-logger`: deleted texts can be kept (one requirement added, one modified).

## Impact

`packages/xincord-plugins/src/xincord/plugins/chat_logger/` (`config.py`, `config.yaml`,
`messages.py`, `cog.py`) and its tests. No stored data changes shape; a kept message is a stored
message, so a later edit or deletion of the same ID, which Discord does not send, would be treated
as one.
