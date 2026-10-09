## Context

v3's `ComponentIdManager` (`ComponentIdManager.kt:49-247`) maps each plugin's declared fields to
the letters `a` to `z` in declaration order and builds `{prefix}{letter}:{value};...`. Values pass
through the global placeholder substitutor, `Int` and `Long` fields are written in lowercase hex,
and nothing is escaped, so a value with `:` or `;` cannot be parsed back. Prefixes come from each
plugin's `info.yaml` (`component_prefix`, such as `ticket@`) or default to the lowercase plugin
name plus `@` (`PluginLoader.kt:277-285`). Panels on Discord still carry these IDs.

## Goals / Non-Goals

**Goals:** a versioned, escaped format within Discord's 100 characters; decoding every v3 ID that
plugins built; converting legacy IDs so messages can be upgraded the first time they are used.

**Non-Goals:** routing interactions and editing messages (command-tree), mass re-sending panels
(never, decision B9).

## Decisions

- **Format.** `{namespace}:1:{letter}={value};...`. The namespace (`[a-z0-9_-]+`) names the plugin
  for routing; `1` is the format version, raised only if the encoding itself changes. A legacy
  prefix ends with `@`, which a namespace cannot contain, so the two formats never collide.
- **Keys.** Letters by position keep IDs short: with full field names, the busiest v3 IDs
  (Feedbacker's four fields with two snowflakes) would exceed 100 characters. A plugin's
  field list starts with its v3 fields in v3 order and is append-only, so one list serves both
  formats; each plugin's golden tests lock it.
- **Values** are text, percent-encoded with nothing left unescaped but `A-Z a-z 0-9 _ . - ~`.
  Integers are accepted when building and written in decimal; parsing always returns text, and
  plugins convert. v3 hex fields decode to the same decimal text, so a legacy and an upgraded ID
  parse to the same map.
- **No placeholders.** The codec writes values as given. Templates render their `uid` values
  before calling the builder; code passes final values.
- **Upgrade.** `ComponentIds.upgrade` parses a legacy ID and builds the new one. `upgrade_view`
  walks a view rebuilt with `View.from_message` or `LayoutView.from_message` and rewrites the IDs
  of buttons and selects in place (the view is a fresh copy), returning whether the message needs
  an edit. Errors propagate to the caller, which logs them and leaves the message alone.

### v3 behaved differently

- v3 behaved differently: values containing `:` or `;` produced IDs that could not be parsed; they
  are now escaped.
- v3 behaved differently: ID values went through the shared placeholder substitutor, so a value
  that contained `%key%` was expanded; values are now written verbatim.
- v3 behaved differently: IDs had no version; new IDs carry one, and legacy IDs are rewritten when
  they are next used.

## Risks / Trade-offs

- Letters tie the new format to field order, as in v3. The append-only rule and per-plugin golden
  tests guard it; a breaking change would raise the format version.
- Escaping makes non-ASCII values long (up to 9 characters each); IDs carry identifiers, not prose.

## User-visible changes

None. Old buttons keep working; their IDs change silently after their first use.
