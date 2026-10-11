## Why

`/dynamic-voice-channel bind` asks for two name formats, but v3 only ever used the first: the
second was stored and never read (v3's own example used `%dvc@info%`, a placeholder v3 never had).
On 2026-10-12 the owner, who had forgotten what it was for, asked to remove it.

## What Changes

- `bind` takes `channel` and `format-name-1` only; `format-name-2` leaves the command and both
  bundled `register.yaml` files. **User-visible**: administrators no longer fill a second format.
- A binding has one format. v3's `formatName2` is ignored when read, whatever its value (before, a
  value other than text made the guild's bindings unreadable), and left out when the guild's
  bindings are written; v3 reads entries without it as an empty text.
- Operators' exported `register.yaml` files that still hold `format-name-2` keep loading; the keys
  are unused.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `plugin-dynamic-voice-channel`: the stored entry, `bind` and the command lose the second format;
  one requirement added for v3's `formatName2`.

## Impact

`packages/xincord-plugins/src/xincord/plugins/dynamic_voice_channel/` (`cog.py`, `store.py`, the two
`register.yaml`), its tests and golden file. No migration: stored entries keep reading.
