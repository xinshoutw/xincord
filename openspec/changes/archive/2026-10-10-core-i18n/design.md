## Context

In v3, `PluginEvent.load()` exports the jar's `lang/` to `plugins/<Name>/lang/`, overwriting only
with `--force-renew-lang-resources` (`PluginEvent.kt:24-37`). `StringLocalizer` decodes each
locale's `register.yaml` into a typed Kotlin class and flattens it by Kotlin property names
(`StringLocalizer.kt:69-90`); a decoding error is logged and that locale silently disappears.
Message and modal templates are read by `MessageCreator` and `ModalCreator` per locale.

## Goals / Non-Goals

**Goals:** keep the file layout and YAML keys; one lang object per plugin; fail at load for broken
files instead of at click time.

**Non-Goals:** parsing templates, substituting placeholders, registering commands.

## Decisions

- **Module** `xincord.core.i18n`: `export_lang(bundled, target, force=...)`, `Lang.load(plugin,
  directory, default_locale)`, `Lang.text`, `Lang.template`, `Lang.localization`,
  `Lang.command(default, key)` and `Translator`. `LangError` reports structural problems.
- **Keys are YAML paths** joined with dots (`basic-calculate.options.formula.name`), not Kotlin
  property names. Text files other than `register.yaml` are addressed as `<file stem>.<path>`
  (`placeholder.empty`). Templates are addressed as `<kind>/<stem>` (`message/welcome`), from
  `message/` and `modal/` with `.yml` or `.yaml`.
- **Locales** are the values of `discord.Locale` (`en-US`, `zh-TW`, ...). The default locale is
  chosen by each plugin.
- **Fallback.** Texts fall back per key and templates per file to the default locale. Command
  localizations never fall back: the translator is asked for every Discord locale, and falling
  back would show the default locale's language to everyone; returning nothing lets Discord show
  the base name from code.
- **Translator.** `Lang.command(default, key)` returns `locale_str(default, lang=self, key=key)`.
  The translator reads both extras, so it needs no registry and a reloaded plugin brings its new
  lang with its new commands.
- **Name rules.** Discord command names: 1 to 32 characters, each a letter, number, mark, `-`,
  `_` or `'`, and lowercase where the character has a lowercase form. Descriptions: 1 to 100
  characters.

### v3 behaved differently

- v3 behaved differently: a `register.yaml` that failed to decode was logged and that locale was
  dropped (`StringLocalizer.kt:61-63`); it now fails the plugin's load.
- v3 behaved differently: an invalid localized command name surfaced only as a failed command
  registration; it is now rejected when the lang files load.
- v3 behaved differently: lookup keys were Kotlin camelCase property paths; they are now the YAML
  keys.

## Risks / Trade-offs

- Validation is stricter than Discord in one way: it checks every `name` in `register.yaml`, so
  any non-command entry called `name` must follow the same rules. None of the v3 files has one.

## User-visible changes

None for Discord users. For the operator: a broken lang file now disables the plugin with an error
that names the file and key.
