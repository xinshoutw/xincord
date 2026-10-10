## Context

On 2026-10-10 the owner renamed nine plugins (`docs/porting/decisions.md`, Amendment 1, amending
B18). Six are ported, and the repository still uses their v3 names: the entry point (the name an
operator lists under `plugins:`), the directory `plugins/<Name>/` that the core derives from it,
the package, the cog class, log lines, WelcomeByeGuild's store namespace, Feedbacker's new-format
component ID namespace and `/feedbacker`, the OpenSpec capabilities, the tests and the fixtures.
The other three (TicketAddons, NtustManager, NtustCourse) are not ported yet; their ports use the
new names (`port-ticket-away-notice` and so on).

xincord has no deployed data: no installation has run it (the cutover waits for parity, C2), so
no store holds a `WelcomeByeGuild` document, no message carries a `feedbacker:1:` ID and no
operator has a `plugins/<old name>/` directory written by xincord. v3 installations are a
different matter: `xincord.core.migrate_v3` (B6) turns a v3 directory into an xincord one, and v3
kept each plugin's files in `plugins/<v3 name>/` (`PluginEvent.kt:21`).

## Goals / Non-Goals

**Goals:** the new names everywhere that names a plugin, except where v3 compatibility needs the
old ones; no other behavior change; a migrated v3 directory that lists and finds the renamed
plugins; capabilities under the new names with `openspec validate --all --strict` passing.

**Non-Goals:** porting the three unported plugins; the follow-up changes of the same day
(UptimeHeartbeat's host-only failure logs and pushes that never stop, CustomCommands from the
config, ChatLogger's own files and five-year default); the v3 data import (Amendment 2), which
will write the new store namespaces; placeholder keys.

## Decisions

### Names

| v3 name | xincord name | Package | Capability | Store namespace | Component IDs |
|---|---|---|---|---|---|
| _Example | Example | `example` (unchanged) | `plugin-example` | none | `example:1:`, no legacy prefix |
| BasicCalculator | Calculator | `calculator` | `plugin-calculator` | none | none |
| SimpleCommand | CustomCommands | `custom_commands` | `plugin-custom-commands` | none | none |
| WelcomeByeGuild | WelcomeGoodbye | `welcome_goodbye` | `plugin-welcome-goodbye` | `WelcomeGoodbye` | none |
| IntervalPusher | UptimeHeartbeat | `uptime_heartbeat` | `plugin-uptime-heartbeat` | none | none |
| Feedbacker | Feedback | `feedback` | `plugin-feedback` | none | `feedback:1:`, legacy `feedbacker@` |
| TicketAddons | TicketAwayNotice | not ported | | | |
| NtustManager | NtustAnnouncements | not ported | | | |
| NtustCourse | NtustCourseWatch | not ported | | | |

- Entry points: `Example`, `Calculator`, `CustomCommands`, `WelcomeGoodbye`, `UptimeHeartbeat`,
  `Feedback`; the core derives `plugins/<Name>/` and the plugin's log name from them.
- Cog classes take the new names (`Calculator`, `CustomCommands`, `WelcomeGoodbye`,
  `UptimeHeartbeat`, `Feedback`; `Example` already had it). Modules inside the packages keep
  theirs (`calculator/calculator.py`, `uptime_heartbeat/pusher.py`, `feedback/form.py`).
- WelcomeGoodbye's documents live under the namespace `WelcomeGoodbye` and its locks are
  `WelcomeGoodbye:<guild ID>`; the document keeps v3's shape. None of the six plugins has a plugin
  table.
- Log lines that name the plugin use the new name (`UptimeHeartbeat listener 1 started (every 60
  s)`, `Feedback cannot post a form in ...`), and logger names follow the packages
  (`xincord.plugins.uptime_heartbeat.pusher`); asyncio task names too (`UptimeHeartbeat listener
  1`).
- Tests and fixtures move to `tests/plugins/<package>/` and `tests/fixtures/plugins/<package>/`;
  test docstrings name the new requirement names. Commit scopes follow the packages
  (`plugin-calculator`).

### What keeps the v3 names

- Legacy component ID prefixes and the decoder: `feedbacker@` (v3's forms are still in guilds).
- Placeholder keys, which operators' templates use: `%_Example@option1%`, `bc_`, `wbg@`, `fb_`.
  The template plugin's `_Example@` keys stay for the same rule, although no v3 operator used
  them (a choice made without the owner; the alternative is `%Example@...%`).
- The inventories under `docs/porting/analysis/` (Calculator's golden answers stay in
  `inventory/fixtures/BasicCalculator-*.jsonl`), Kotlin citations, archived changes,
  `decisions.md`'s original text and the raw submission.
- Every command except `/feedbacker`, and their `register.yaml` keys.

### `/feedback`

- The base name and the en-US name are `feedback`; the `register.yaml` key `feedbacker` becomes
  `feedback` in both locales, and zh-TW keeps its localized name. Options and descriptions are
  unchanged.
- The core uploads a guild's commands as one bulk overwrite when the payload's hash changes, so
  `/feedbacker` disappears from a guild the first time xincord starts there.
- A `register.yaml` copied from v3 (by the migration's directory move or by hand) still has the
  `feedbacker` key: the command then shows its base names (`feedback`, English descriptions) in
  every locale until the file is deleted, so that the bundled one is exported, or edited. The
  manual checks say so.

### No migration of xincord's own data

With no deployed data there is nothing to move: the store namespace, the new-format ID namespace
and the directories change without a migration, and the component ID decoder reads no
`feedbacker:1:` IDs. The v3 data import writes v3's documents under the new namespaces.

### `xincord.core.migrate_v3`

- `RENAMED` maps the nine v3 names to the new ones, the unported three included, so that a v3
  directory that enables them lists the names their ports will register.
- `enabled_v3_plugins(root)` returns the new names, deduplicated and sorted.
- `move_renamed_directories(root)` moves `plugins/<v3 name>/` to `plugins/<new name>/` with
  `Path.rename` (the same file system), and leaves both in place, with a report line, when the
  new one exists. The plugins then find v3's config and lang files, as the other plugins do (B6:
  v3's plugin files load unchanged). It moves every renamed plugin's directory, enabled or not:
  the files are the operator's.
- `migrate_directory(root)` reads the enabled plugins first, moves the directories after the new
  core config validates and before the backup and the new config are written, so that a failed
  move leaves the v3 config in place and a second run tries again. A directory that is already
  migrated, or has a backup, moves nothing.

### Capabilities

OpenSpec 1.14.1 cannot rename a capability. Each renamed plugin's requirements are ADDED, with the
new names, to a new capability whose delta `## Purpose` seeds the new spec, and REMOVED from the
old one with a reason and a migration; `.openspec.yaml` declares `retire_capabilities: true`, so
that `archive` deletes the five emptied specs instead of refusing to write a spec without
requirements. `plugin-example` keeps its capability: its first requirement is RENAMED and
MODIFIED. `core-config` modifies the migration's requirement and adds one for the directories.

### Tests (xfail-first)

Per plugin, the tests whose expectations the rename changes (the entry point and directory, and
WelcomeGoodbye's namespace, a UptimeHeartbeat log line, `/feedback` and the `feedback:1:` IDs)
are committed first with the new names, marked `xfail(strict=True)` without `raises` (no stub can
stand for a missing entry point); the rename commit removes the markers and updates the remaining
tests. The migration's tests follow the same pattern.

## v3 behaved differently

Not applicable: the change ports no v3 behavior and fixes no v3 defect.

## User-visible changes (for the owner)

- Names in the core config's `plugins:`: Example, Calculator, CustomCommands, WelcomeGoodbye,
  UptimeHeartbeat, Feedback (v3: _Example, BasicCalculator, SimpleCommand, WelcomeByeGuild,
  IntervalPusher, Feedbacker).
- Their files live in `plugins/Example/`, `plugins/Calculator/`, `plugins/CustomCommands/`,
  `plugins/WelcomeGoodbye/`, `plugins/UptimeHeartbeat/` and `plugins/Feedback/`.
- `/feedbacker` is `/feedback` (zh-TW clients keep seeing the localized name).
- Log lines and logger names use the new names.
- `python -m xincord.core.migrate_v3 <dir>` lists the new names and moves the renamed plugins' v3
  directories, with a report line each.

## Manual checks

1. Image (done in this change, `tasks.md` 8.1): `docker compose build`, then `docker compose run
   --rm -T bot --no-online` with a temporary `bot/config.yaml` that enables every ported plugin
   (and `plugins/Economy/config.yaml` with an example `admin_id`). Done on 2026-10-10: it exited 0,
   logged `Plugins loaded:` with all thirteen and wrote their files under the new directory names;
   `docker compose down -v` and removing `bot/` cleaned up. Before that, the wheel from
   `uv build --package xincord-plugins` listed the six packages under their new names with their
   `config.yaml` and `lang/` files, and the new entry points.
2. At cutover, after `python -m xincord.core.migrate_v3 <dir>`: `plugins:` lists the new names and
   the renamed plugins' directories moved; delete `plugins/Feedback/lang/*/register.yaml` (v3's,
   with the `feedbacker` key) so that the bundled files are exported.
3. In a test guild: after the first start, `/feedback` is there and `/feedbacker` gone; a star of a
   form posted by v3 still opens the modal.

## Risks / Trade-offs

- A missed reference to an old name: the tests load every plugin through its entry point, the image
  check loads all thirteen, and a search for the old names outside the inventories, the archive and
  Kotlin citations comes up empty.
- An operator's v3 `register.yaml` for Feedback loses its localizations until it is renewed (see
  `/feedback`); keeping the `feedbacker` key instead would keep `/feedbacker` for en-US clients.
