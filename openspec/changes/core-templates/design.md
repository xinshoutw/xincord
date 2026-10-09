## Context

Plugins use v3's `messagecreator.v2.MessageCreator` and `messagecreator.modal.ModalCreator`. The v2
creator decodes the v1 schema with KAML in non-strict mode and renders it through the v1
`MessageBuilder` (`v1/builder/MessageBuilder.kt`): every text goes through the substitutor, URL
fields are kept only when they start with `http`, empty embeds are dropped, `color_code` uses
`java.awt.Color.decode`, `timestamp` is `%now%` or epoch milliseconds, and `model_key` swaps in a
JDA object from the caller's `modelMapper`. Component IDs come from the plugin's
`ComponentIdManager`.

## Goals / Non-Goals

**Goals:** render every shipped template the way v3 did; fail at load for a broken template; keep
the ID format out of this module.

**Non-Goals:** Components V2, the ID codec, interaction routing, sending messages.

## Decisions

- **Module** `xincord.core.templates`: `load_message(path)`, `load_modal(path)`,
  `Templates.load(lang)` (every template of every locale, keyed by locale and name),
  `render_message(template, values, build_id=..., models=...)` returning `Message(content,
  embeds, view)` with `kwargs()` for `send` and `edit`, and `render_modal(...)` returning a
  `discord.ui.Modal`.
- **YAML tags.** A `SafeLoader` subclass maps the three tags to mappings with a `type`
  discriminator (`buttons`, `string_select`, `entity_select`); pydantic models validate the
  result. Template models extend the config `Model` (frozen, unknown keys kept) with
  `coerce_numbers_to_str`, so `uid: {id: 123}` stays a string as in KAML. The config module's
  unknown-key walker becomes public as `unknown_keys`.
- **Validation at load** covers what v3 checked only at render time: button styles 1 to 5, link
  buttons have `url`, other buttons and selects have `uid` (unless `model_key`), exactly one of
  `formatted` or `model_key` for button emojis, entity targets `USER`, `ROLE` or `CHANNEL`, channel
  types required for `CHANNEL` and named like JDA's `ChannelType`, `color_code` (unless it uses a
  placeholder) and `timestamp` formats.
- **IDs.** `build_id(uid)` receives the `uid` map with placeholders already applied. v3 applied
  placeholders before encoding for buttons but after encoding for selects and modals
  (`MessageBuilder.kt:232-262`, `ModalBuilder.kt:15-18`); one order for all removes that
  difference.
- **Views.** Components render into a `discord.ui.View(timeout=None)` that is stopped before it is
  returned: discord.py stores and dispatches only unfinished views
  (`Messageable.send`), and component interactions are routed by the core instead (Core change
  `command-tree`). Modals are stopped for the same reason.
- **Models.** Message: `Message`; embed: `discord.Embed`; field: `EmbedField`; row: a sequence of
  `discord.ui.Item`; button: `discord.ui.Button`; button emoji: `discord.PartialEmoji` or `str`;
  option: `discord.SelectOption`; modal: `discord.ui.Modal`; text input: `discord.ui.TextInput`.
- **Emoji** strings go through `discord.PartialEmoji.from_str`, which accepts custom
  (`<:name:id>`) and Unicode emoji like JDA's `Emoji.fromFormatted`.
- **Modal inputs** use discord.py's `TextInput(label=...)`; v3's JDA 6 wrapped each input in a
  `Label` component, which renders the same.

### v3 behaved differently

- v3 behaved differently: a template present in a locale directory but missing a file that the
  default locale has raised at render time (`MessageCreator.kt:87-91`); lookups now fall back per
  file (core-i18n).
- v3 behaved differently: rendering with a `replaceMap` added the values to the shared global
  substitutor permanently (`MessageCreator.kt:57-68`); values now apply to one render only.
- v3 behaved differently: invalid styles, missing `uid`s and bad timestamps failed when a message
  was sent; they now fail when the plugin loads.

## Risks / Trade-offs

- Stricter load-time validation may reject a hand-edited template that v3 tolerated until the
  broken part was rendered. The error names the file and the field.

## User-visible changes

None for Discord users. For the operator: a broken template disables its plugin at startup with
the file named.
