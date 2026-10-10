## Why

On 2026-10-10 the owner renamed nine plugins (`docs/porting/decisions.md`, Amendment 1, which
amends B18). Six of them are ported and still carry their v3 names in the entry points, the
`plugins/<Name>/` directories, the packages, a store namespace, a component ID namespace, the
tests and the OpenSpec capabilities. A v3 installation migrated with `xincord.core.migrate_v3`
would also list the v3 names in `plugins` and keep its files in the v3 directories, where the
renamed plugins no longer look.

## What Changes

- Six ported plugins take their new names for the entry point (the name in `plugins:`), the
  `plugins/<Name>/` directory, the package, the cog class, the log lines, the tests and the test
  fixtures: _Example -> Example (package `example` unchanged), BasicCalculator -> Calculator
  (`calculator`), SimpleCommand -> CustomCommands (`custom_commands`), WelcomeByeGuild ->
  WelcomeGoodbye (`welcome_goodbye`), IntervalPusher -> UptimeHeartbeat (`uptime_heartbeat`),
  Feedbacker -> Feedback (`feedback`).
- WelcomeGoodbye keeps its documents in the store namespace `WelcomeGoodbye`; Feedback's
  new-format component IDs start with `feedback:1:`. v3's legacy prefix `feedbacker@` and its
  decoding stay, so that v3's forms keep working.
- `/feedbacker` becomes `/feedback`: the base name, the en-US name and the `register.yaml` key in
  both locales. The other commands keep their names.
- `xincord.core.migrate_v3` writes the new names in `plugins` and moves the v3 directory of each
  renamed plugin to its new name (all nine renames, the three unported plugins included).
- The capabilities `plugin-basic-calculator`, `plugin-simple-command`, `plugin-welcome-bye-guild`,
  `plugin-interval-pusher` and `plugin-feedbacker` are retired; their requirements continue, with
  the new names, in `plugin-calculator`, `plugin-custom-commands`, `plugin-welcome-goodbye`,
  `plugin-uptime-heartbeat` and `plugin-feedback`.
- Docs: the porting guide, the port-plugin skill, `HANDOFF.md` and the review queue use the new
  names; the v3 names stay in the inventories, in Kotlin citations and in the archived changes.

Kotlin sources (the v3 names being mapped):
- `XsDiscordBotKt@3a59607:Core/src/main/kotlin/core/plugin/PluginEvent.kt:21` (`plugins/<name>`)
- `XsDiscordBotKt@3a59607:Plugins/Feedbacker/src/main/kotlin/feedbacker/command/Register.kt:22-35`
  (`/feedbacker`)

Out of scope: porting TicketAddons (TicketAwayNotice), NtustManager (NtustAnnouncements) and
NtustCourse (NtustCourseWatch), whose ports use the new names; the follow-up changes the owner
asked for on the same day (UptimeHeartbeat's host-only failure logs and pushes that never stop,
CustomCommands defined in the config, ChatLogger's own files and five-year default, the v3 data
import); placeholder keys, which keep v3's names (`%_Example@option1%`, `wbg@`, `fb_`).

## Capabilities

### New Capabilities

- `plugin-calculator`: BasicCalculator's requirements under the name Calculator.
- `plugin-custom-commands`: SimpleCommand's requirements under the name CustomCommands.
- `plugin-welcome-goodbye`: WelcomeByeGuild's requirements under the name WelcomeGoodbye, with the
  store namespace `WelcomeGoodbye`.
- `plugin-uptime-heartbeat`: IntervalPusher's requirements under the name UptimeHeartbeat.
- `plugin-feedback`: Feedbacker's requirements under the name Feedback, with `/feedback` and the
  component ID namespace `feedback`.

### Modified Capabilities

- `plugin-example`: the plugin installs as Example.
- `core-config`: the migration lists renamed plugins under their new names and moves their
  directories.
- Retired (all requirements removed, `retire_capabilities: true`): `plugin-basic-calculator`,
  `plugin-simple-command`, `plugin-welcome-bye-guild`, `plugin-interval-pusher`,
  `plugin-feedbacker`.

## Impact

`packages/xincord-plugins/pyproject.toml` (entry points), five plugin packages and their tests and
fixtures move; `xincord.core.migrate_v3` gains the rename table and the directory moves. Operators
list the new names in `plugins:` and find the files under the new directories. xincord has no
deployed data, so no store or component ID migration is needed. No new dependencies.
