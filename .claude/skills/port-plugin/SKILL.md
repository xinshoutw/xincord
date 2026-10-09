---
name: port-plugin
description: Port one XsDiscordBotKt plugin to xincord following the project's OpenSpec and xfail-first rules. Use when starting or continuing the port of a named plugin (for example "port AutoRole").
---

# Port a plugin

Work on one plugin at a time, in the order of decision C1. Follow `AGENTS.md` throughout. The
first plugins calibrate this checklist: fix it here when reality differs.

1. **Read.** `docs/porting/analysis/inventory/<Plugin>.md` end to end, then the Kotlin files it
   cites at `XsDiscordBotKt@3a59607`. Note every v3 defect the inventory lists.
2. **Propose.** `openspec new change port-<plugin-kebab>`, then write:
   - `proposal.md`: scope, out of scope, cited Kotlin sources.
   - `specs/plugin-<plugin-kebab>/spec.md`: one requirement per behavior, scenarios testable
     without Discord.
   - `design.md`: config schema, storage tables, component IDs (legacy prefix and v3 field
     order), "v3 behaved differently: ..." entries, and the user-visible changes.
   - `tasks.md`: one xfail task and one implementation task per requirement.
   Run `openspec validate port-<plugin-kebab> --strict` and commit the proposal.
3. **Resources.** Port the config and lang YAML with example values only; never real IDs,
   account numbers or tokens.
4. **Per requirement, xfail-first.** Test (fails for the expected reason) -> commit with
   `xfail(strict=True)` -> implement and remove the marker -> commit. Pure logic is tested without
   discord.py; Cogs and views get Protocol fakes.
5. **Wire it up.** Register the extension in the `xincord.plugins` entry-point group in
   `packages/xincord-plugins/pyproject.toml`, named after the v3 plugin (`AutoRole = ...`).
   Declare `DEPENDS`, `SOFT_DEPENDS` and `INTENTS` as module constants, and keep import time free
   of work. In `setup(bot)`, get `bot.plugin_context(__name__)` and load `config(Model)` from the
   bundled `config.yaml` and `lang(default_locale)`. Drop v3's `enabled` key: the core config's
   `plugins` list decides. v3 `globalCommands()` become commands with `extras={"global": True}`;
   a command that opens a modal sets `extras={"defer": False}`. Buttons, selects and modals reach
   the plugin through `bot.route(__name__, IDS, handler)`.
6. **Golden tests.** Declare the plugin's `ComponentIds(namespace, fields, legacy_prefix=...,
   legacy_hex=...)` with the v3 fields first, in v3 declaration order (append only). Decode real
   v3 IDs from the inventory and check that each upgrades to the expected new ID. Render every
   shipped template in each locale.
7. **Document.** Add the mapping notes, new pitfalls and the differences table rows to
   `docs/porting-guide.md`. Write the manual smoke checklist for a test guild in the change's
   `design.md`.
8. **Close.** Run `scripts/gate.sh`, push, check CI, `openspec archive port-<plugin-kebab> --yes`,
   `openspec validate --all --strict`, commit and push. Report the user-visible changes to the
   owner.
