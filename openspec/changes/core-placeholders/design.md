## Context

v3's `Substitutor` wraps commons-text `StringSubstitutor` with `%` delimiters and `$` escape
(`Substitutor.kt:80-86`). commons-text substitutes inside resolved values by default, so values
are expanded recursively. `Placeholder` keeps one substitutor per user and per member in
unsynchronized maps shared by every plugin (`Placeholder.kt:19-42`), and plugins add custom keys
to them with `Placeholder.update` (Economy). The `put*` helpers add key families with an optional
prefix and lazy suppliers that fall back to defaults (`Placeholder.kt:145-287`).

## Goals / Non-Goals

**Goals:** identical output to v3 for the shipped templates; no recursion; no shared state; key
families testable without Discord.

**Non-Goals:** interaction keys (Core change `command-tree`), plugin keys, lazy evaluation.

## Decisions

- **Scanner.** `render` scans for `%`. With a `$` right before it (and not already consumed), it
  emits `%` and moves on. Otherwise it looks for the next `%`; if the text between is a key with a
  value, it emits the value and continues after the closing `%`; if not, it emits the opening `%`
  and continues at the closing `%`, which may open the next placeholder. This matches commons-text
  except that values are never rescanned.
- **Fresh context.** Families are plain functions returning `dict[str, str]`; callers merge the
  dicts they need into a new dict per render. Custom keys that v3 stored per user are passed by the
  plugin at render time.
- **Inputs are Protocols** (`UserLike`, `MemberLike`, `RoleLike`, `GuildLike`, `ChannelLike`,
  `AssetLike`) that discord.py's `User`, `Member`, `Role`, `Guild` and channels satisfy; tests use
  small fakes, and a type-only test checks the discord.py classes against them.
- **v3 formats kept:** none value `-`, `0` for ids and counts, `false` for `user_is_bot`; ISO-8601
  times in JDA's `OffsetDateTime.toString()` style (`2026-01-02T03:04:05.678Z`, fraction only
  when non-zero, 3 or 6 digits); channel types and locales as JDA enum names; roles joined with a
  space (mentions) or `, ` (names), highest role first, default role excluded.
- **Eager values.** Every value is computed when the family is built. discord.py serves them from
  its cache, so the laziness v3 needed is unnecessary.
- **Locale table** `resources/locales.yaml` maps each Discord locale to JDA 6.4.1's enum name and
  native name. It is YAML because native names contain CJK characters (decision A5).
- **Owner.** `guild_owner_id` and `guild_owner_mention` use `Guild.owner_id`, which discord.py
  always has; v3 read the cached owner member and fell back to `0` and `-`.

### v3 behaved differently

- v3 behaved differently: substituted values were expanded again, so user-controlled text (names,
  nicknames, channel names) could inject other placeholders, and a self-reference threw and the
  message was not sent (`Substitutor.kt:80-86`). Values are now inserted verbatim.
- v3 behaved differently: per-user substitutors were cached in shared, unsynchronized maps and kept
  every custom key a plugin ever set (`Placeholder.kt:19-42`). Each render now builds its own
  values.
- v3 behaved differently: `guild_owner_id` and `guild_owner_mention` were `0` and `-` when the
  owner member was not cached.

## Risks / Trade-offs

- A template that relied on recursive expansion breaks. None of the shipped templates does.

## User-visible changes

Names, nicknames and channel names that contain `%...%` now appear literally instead of being
expanded.
