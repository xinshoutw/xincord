## Context

v3's `bind` required `format-name-1` and `format-name-2` and stored both in
`plugins/DynamicVoiceChannel/data/<guild>.json`; only `formatName1` named rooms. The port kept the
option and the field for v3's command and documents, stored and unused.

## Goals / Non-Goals

**Goals:** one name format in the command and the bindings; v3's documents and lang files keep
loading.

**Non-Goals:** renaming `format-name-1` or its texts (`名稱格式1`, `name-format-1`); a new use for a
second format.

## Decisions

### Ignore `formatName2`, write new entries without it

Reading takes `categoryId`, `defaultName` and `formatName1` and ignores every other field, as Moshi
ignored unknown ones; `bind` writes its new entry without `formatName2` and keeps the guild's other
entries as stored, as it always did. v3's data class defaults a missing `formatName2` to an empty
text, so the documents stay readable by v3. Alternative: keep writing `"formatName2": ""` (v3's
shape to the letter, for a field that nothing reads).

### Exported lang files

`Lang` compares only the locales' keys with each other, and the command looks up its keys by name,
so `format-name-2` keys left in an operator's files are unused, without a warning while every
locale holds them. `--force-renew-lang-resources` rewrites the files without them.

## Manual check

None beyond the tests: the command payload is compared with the golden file.
