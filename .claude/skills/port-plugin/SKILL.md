---
name: port-plugin
description: Port one XsDiscordBotKt plugin to xincord following the project's OpenSpec and xfail-first rules. Use when starting or continuing the port of a named plugin (for example "port AutoRole").
---

# Port a plugin

Work on one plugin at a time, in the order of decision C1. Follow `AGENTS.md` throughout. The
template is _Example: `packages/xincord-plugins/src/xincord/plugins/example/`, its tests in
`tests/plugins/example/` and its archived change `openspec/changes/archive/*-port-example/`. Copy
its shape and the conventions below. Fix this skill when reality differs; the newest port wins.

Names: `<Plugin>` is the v3 name (`AutoRole`, `_Example`), `<kebab>` its kebab case (`auto-role`,
`example`) for the change and the commit scope, `<package>` the Python package (`auto_role`,
`example`).

## Steps

1. **Read.** `docs/porting/analysis/inventory/<Plugin>.md` end to end, then the Kotlin files it
   cites at `XsDiscordBotKt@3a59607` (in ranges). Note every v3 defect the inventory lists.
2. **Propose.** `openspec new change port-<kebab>`, then write:
   - `proposal.md`: scope, out of scope, cited Kotlin sources.
   - `specs/plugin-<kebab>/spec.md`: one requirement per behavior, scenarios testable without
     Discord, each requirement under 500 characters.
   - `design.md`: package, config schema, storage tables, component IDs (legacy prefix and v3 field
     order), "v3 behaved differently: ..." entries, user-visible changes, manual smoke checklist.
   - `tasks.md`: resources, one xfail task and one implementation task per requirement, then
     conventions, docs and close.
   Run `openspec validate port-<kebab> --strict`, the gate, and commit
   (`docs(plugin-<kebab>): propose port-<kebab>`).
3. **Resources.** Copy v3's `config.yaml` and lang files into the package (fix missing final
   newlines and CRLF line endings), example values only: never real IDs, account numbers or
   tokens.
4. **Per requirement, xfail-first.** Test (fails for the expected reason; check with
   `pytest --runxfail`) -> commit with `xfail(strict=True)` -> implement and remove the marker ->
   commit. Tick `tasks.md` in the same commits.
5. **Wire it up.** Entry point, `setup`, command, routes: see the conventions.
6. **Golden tests.** v3's text per locale in `golden.yaml`; v3 component IDs from the inventory
   decode and upgrade to the expected new IDs (a plugin with v3 components); every shipped template
   renders in each locale. Recorded v3 answers (BasicCalculator's JSONL) are copied unchanged; a
   record that a fixed v3 defect changes must agree with an independent implementation in the test
   (`tests/plugins/basic_calculator/test_golden.py`), never be edited.
7. **Check the package.** `uv build --package xincord-plugins -o <scratch dir>` lists `config.yaml`
   and `lang/` in the wheel. Stronger: install both wheels in a scratch venv and run
   `xincord --no-online` in an empty directory whose `config.yaml` enables the plugin.
8. **Document.** `docs/porting-guide.md`: differences rows, new pitfalls, convention changes. Audit
   the inventory: each behavior is a scenario with a test, or out of scope or a v3 difference in
   `design.md`, with the reason.
9. **Close.** Gate, push, CI green; `openspec archive port-<kebab> --yes`,
   `openspec validate --all --strict`; `HANDOFF.md` (sections 4, 5, 7) and the plugin's section in
   `docs/porting/owner-review.md`; commit, push, CI green.

## Conventions

### Package

```
packages/xincord-plugins/src/xincord/plugins/<package>/
  __init__.py   DEPENDS, SOFT_DEPENDS, INTENTS, DEFAULT_LOCALE and setup(bot)
  config.py     class Config(Model), if the plugin has settings
  cog.py        the Cog: command builders, handlers, listeners; IDS
  config.yaml   the bundled default config
  lang/<locale>/register.yaml, message/*.yaml, modal/*.yaml
```

- Import the plugin's own modules relatively (`from .cog import Example`). Split `cog.py` when it
  grows: pure logic in its own module (tested without discord.py, as
  `basic_calculator/calculator.py`), storage in `store.py`. Run CPU-bound work with
  `asyncio.to_thread`.
- Entry point: `<Plugin> = "xincord.plugins.<package>"` under
  `[project.entry-points."xincord.plugins"]` in `packages/xincord-plugins/pyproject.toml`. The name
  is the v3 name: the `plugins:` entry, the `plugins/<Plugin>/` directory and the log name. `uv run`
  reinstalls the workspace package; `uv.lock` does not change.
- `uv_build` ships every file in the package, so bundled YAML reaches the image.

### setup

```python
async def setup(bot: Bot) -> None:
    context = bot.plugin_context(__name__)  # __name__ is the entry-point module
    lang = context.lang(DEFAULT_LOCALE)
    cog = Example(context.config(Config), lang, Templates.load(lang))
    await bot.add_cog(cog)
    bot.tree.add_command(cog.command())
    bot.route(__name__, IDS, cog.count)
```

- Discovery imports the module and `load_extension` runs it again: no work at import time.
- `setup` runs before the gateway connects (without a login under `--no-online`): wait for
  `bot.wait_until_ready()` or `on_ready` for guild data; stop loops in `cog_unload`.
- Unloading and reloading remove the cog, the tree commands whose callback lives in the package and
  the routes; release anything else in `cog_unload`.
- `DEFAULT_LOCALE` is v3's default locale (zh-TW in every v3 plugin so far).

### Config

- `class Config(Model)` with the same defaults as the bundled `config.yaml`. Keep v3's YAML keys and
  shapes so v3 files load unchanged; v3's `enabled` only logs `unknown key enabled`. A renamed key
  needs a migration in `xincord.core.migrate_v3` (none so far).
- A plugin whose only v3 key was `enabled` ships no `config.yaml` and never calls
  `context.config`.

### Commands

- Build commands in `setup` from the Lang: `Translator` reads the Lang from each string's extras,
  and the Lang loads only in `setup`. Pattern: `Example.command()` in the template.
- The callback is the cog's bound method (`callback=self.example_command`): discord.py makes the
  cog the command's binding, so `cog_app_command_error` and the cog's `interaction_check` apply as
  for a decorated cog command. Localize the options by calling `app_commands.rename(...)` and
  `app_commands.describe(...)` on the built command, with values
  `lang.command(<v3 default>, "<register.yaml key>")`.
- Keep `import discord` (and every name in the callback's annotations) at runtime: discord.py
  evaluates the annotations when the command is built. ruff does not flag a move into
  `TYPE_CHECKING`; the plugin's tests do, because the plugin stops loading.
- Base names and descriptions are v3's `Commands.slash(...)` defaults. Limits use
  `app_commands.Range`. Guild command by default; v3 `globalCommands()` get `extras={"global":
  True}`; a command that opens a modal sets `extras={"defer": False}`. The tree defers the others
  ephemerally before the callback runs: answer with `interaction.edit_original_response(...)` or
  `interaction.followup.send(...)`.
- A v3 reply posted with `event.channel.sendMessage(...)` after the defer: send it to
  `interaction.channel` when that has `send` (a `runtime_checkable` Protocol, so fakes need no
  discord base class; forums and categories have none), then `delete_original_response()`; on
  `discord.HTTPException`, edit the deferred response into it instead (BasicCalculator's `_post`).

### Templates and placeholders

- `Templates.load(lang)` in `setup`, so a broken template disables the plugin at load. Render with
  `render_message(templates.message(name, interaction.locale.value), values, build_id=IDS.build)`.
- v3's `Placeholder.get(event)` is `actor_values(interaction.user, bot) |
  interaction_values(interaction)` (`placeholder_values` in the template's `cog.py`);
  `Placeholder.get(member)` is `actor_values(member, bot)`. When a second plugin needs
  `placeholder_values`, move it to `xincord.core.placeholders` (core change with a spec delta)
  instead of copying it again.
- Plugin keys keep v3's names (`_Example@option1`, `ga@title`) so operators' templates keep working.

### Components

- `IDS = ComponentIds("<package>", fields, legacy_prefix=..., legacy_hex=...)` in `cog.py`: v3's
  fields first, in v3 declaration order (`action` first in every v3 plugin), new fields appended;
  `legacy_prefix` is v3's `component_prefix` from `info.yaml` or `<lowercase name>@`; `legacy_hex`
  lists the fields v3 declared as `FieldType.INT_HEX` or `LONG_HEX`. A plugin without v3
  components has no legacy prefix.
- Templates set `uid: {action: ..., ...}`; `setup` calls `bot.route(__name__, IDS, handler)`. The
  handler gets `ParsedId` (values are strings), dispatches on `action`, and may raise: the core
  logs it with the plugin's name and upgrades legacy IDs on the message afterwards.
- `interaction.response.edit_message(view=...)` changes only the components; content and embeds
  stay.

### Tests

- `tests/plugins/<package>/test_<topic>.py`. The module docstring cites the Kotlin sources; each
  test's docstring is `Requirement: <name>.`
- `tests/plugins/<package>/conftest.py`: `bot` loads the real plugin with
  `plugin_fakes.load_plugin("<Plugin>", tmp_path / "plugins", store)` (entry point, translator and
  `setup`, no network); `cog` is `bot.get_cog(...)`. To test operator edits and v3 files, write
  them under `tmp_path / "plugins" / "<Plugin>"` first and call `load_plugin` in the test.
- `tests/support/discord_fakes.py`: `FakeInteraction` records what the plugin sends in `sent`;
  `FakeChannel` records `channel.send` into a shared `sent` list or raises its `error`
  (`forbidden()`); `FakeUser`, `buttons(view)` and `embed_dict(embed)`. Extend it instead of
  writing new fakes. pytest runs in importlib mode, so a test module cannot import another one:
  tests that share helpers stay in one module (BasicCalculator's `test_replies.py`).
  Call cog methods directly (`cog.example_command(...)`), check a command's wiring through
  `bot.tree.get_command(...)` (its `binding` is the cog), and send components through
  `bot.on_interaction(...)`, which includes the routing.
- `tests/fixtures/plugins/<package>/golden.yaml`, loaded with `plugin_fakes.golden("<package>")`:
  v3's text per locale. Compare rendered embeds and buttons, and the command payload from
  `CommandTree.payloads()`, with it; no CJK text is typed in Python.
- A test that loads the plugin cannot reach a stub that raises without breaking the load: mark it
  `xfail(strict=True, reason=...)` without `raises`. Give handlers that tests call directly a stub
  and `raises=NotImplementedError`. A test that would already pass (such as "no response") must
  call a stub. A stub whose annotations need `discord` keeps that import under `TYPE_CHECKING`
  and plain types (ruff's TC rules); the imports move to runtime with the code that uses them.
- Pure functions get one requirement each when they can be stubbed separately (BasicCalculator:
  trimming, reading, results, powers, then `calculate` with the golden files), so that each xfail
  commit fails for its own stub.
- Never unload or reload the real plugin in a test: discord.py re-imports its modules, and later
  tests compare against classes from the old ones. The core's reload tests use fake plugins.
- ruff, pyright, pytest and coverage already cover `packages/` and `tests/`; nothing to configure
  per plugin.
