## Context

v3's _Example (`Plugins/_Example`, 5 Kotlin files, 171 lines) is the sample plugin. `Event`
(`PluginEventConfigure`) reads `config.yaml` (`enabled`, `example_key`) and a `StringLocalizer`
(`Event.kt:17-30`), registers one guild command when enabled (`Event.kt:49-55`,
`Register.kt:21-33`) and forwards it to `_Example.onSlashCommandInteraction`, which puts two
`_Example@` keys into the user's cached substitutor and edits the auto-deferred response into the
`example` message in the user's locale (`_Example.kt:24-42`). It is built and shipped in every
BotPack, disabled. Decision C1 ports it first, "rewritten as the template for the new API". The
inventory is `docs/porting/analysis/inventory/_Example.md`.

## Goals / Non-Goals

**Goals:** v3's behavior (an ephemeral embed echoing the options, `none` for a missing `option2`,
the user's locale with a zh-TW fallback); a plugin that shows each part of the API a port needs;
the conventions that later ports follow.

**Non-Goals:** storage, modals, listeners and background tasks (the plugins that need them will
show them); rewriting plugin config files.

## Decisions

### Package, entry point and bundled files

- `packages/xincord-plugins/src/xincord/plugins/example/`: `__init__.py` (the module constants
  `DEPENDS`, `SOFT_DEPENDS`, `INTENTS`, `DEFAULT_LOCALE` and `setup`), `config.py` (the config
  model), `cog.py` (the Cog: command, reply, button handler), `config.yaml` and `lang/`. The
  package uses relative imports, so a copy works under another name.
- The entry point is `_Example = "xincord.plugins.example"`. **_Example is registered**: v3 built
  and shipped it, disabled, in every release; registered, it stays inert until the core config's
  `plugins` list names it, which is the same, and CI exercises the template through the real entry
  point, loader and packaging, so it cannot drift from the API. Discovery imports only enabled
  plugins, so the cost is one entry point. Alternative: leave it unregistered as copy-only code
  that operators cannot enable.
- v3's `info.yaml` keys `author`, `coreApi` and `version` have no counterpart: the plugin's version
  is the `xincord-plugins` distribution's. v3's `Event` logged `_Example is disabled.` when off; a
  plugin missing from `plugins` is never imported (core-plugin-loading).
- uv_build ships every file in the package, so `config.yaml` and `lang/` are in the wheel that the
  image installs with `--no-editable`. Checked on 2026-10-10: the wheel from
  `uv build --package xincord-plugins` lists them and the `_Example` entry point, and
  `xincord --no-online`, run from a scratch virtual environment with both wheels installed and
  `plugins: [_Example]`, loads the plugin, writes `plugins/_Example/` and exits with 0.

### Config

`Config(Model)` has `example_key: str = "example_value"`; the bundled `config.yaml` holds the same
default. The value appears in the reply as `%_Example@example_key%`, a third embed field: a config
value flowing into a template, as BotInfo's source link (C3) will. v3's `enabled` is not part of
the model; a v3 file still loads and logs `unknown key enabled`.

### Command

The Lang is loaded in `setup`, after import, and `Translator` reads it from each string's extras,
so commands are built at setup instead of with class-level decorators. `Example.command()` wraps a
nested callback with `app_commands.rename` and `app_commands.describe` and returns
`app_commands.Command(name=lang.command("example-command", "example.name"), ...)`; `setup` adds it
with `bot.tree.add_command`. A nested function, not a method, is the callback because discord.py
takes a function defined in a class for a method and skips one parameter too many. discord.py
evaluates the callback's annotations when the command is built, so `import discord` stays at
runtime; `app_commands.describe` and `rename` join ruff's `runtime-evaluated-decorators`, so ruff
flags a move into `TYPE_CHECKING` (ruff accepted it before). discord.py removes the
command when the extension unloads, because its callback's module belongs to the extension. Base
names and descriptions are v3's `Commands.slash` defaults; `register.yaml` localizes them. `option1`
is `app_commands.Range[str, None, 1024]`. The command keeps the tree's ephemeral defer (no
`extras`), and the reply edits the deferred response, as v3's `hook.editOriginal` did.

### Reply and placeholders

The values are v3's `Placeholder.get(event)`, `actor_values(interaction.user, bot) |
interaction_values(interaction)`, plus `_Example@option1`, `_Example@option2` (`str(option2)` or
`none`), `_Example@example_key` and `_Example@count` (`0`). The `example` template renders the
embed; the `counter` template renders the button, so a press re-renders only the button. Templates
are loaded once in `setup` (`Templates.load`), so a broken template disables the plugin at load.
`DEFAULT_LOCALE` is zh-TW, as in v3. The footer keeps v3's `❖ ORDERLY SERVER ❖`, which the
inventory lists as hard-coded branding: it lives in the lang templates, which the operator edits.
discord.py dispatches the command by name, which replaces v3's `checkCommandString`.

### Counter button and component IDs

`IDS = ComponentIds("example", ("action", "count"))`: the namespace is the package name, and the
first field is `action`, as in every v3 plugin with components. _Example had no components in v3,
so there is no legacy prefix and no v3 ID to decode. `setup` calls
`bot.route(__name__, IDS, cog.count)`. The handler parses the count, renders `counter` with the
count plus one and answers with `interaction.response.edit_message(view=...)`, which keeps the
embed. A malformed count raises, and the core logs it with the plugin's name.

### Tests

- `tests/plugins/example/`: one file per requirement group; its `conftest.py` loads the plugin
  through its real entry point with `plugin_fakes.load_plugin` (discovery, `setup_hook`, the
  plugin's `setup`) in a temporary directory with an in-memory store.
- `tests/support/discord_fakes.py`: a fake user and a fake interaction that records responses,
  cast to `discord.Interaction`; later plugins extend it.
- `tests/fixtures/plugins/example/golden.yaml`: v3's text by locale (command localizations, the
  embed, the button label); tests compare rendered output with it, so no CJK text is typed in
  Python.
- The `store` fixture moves from `tests/core/conftest.py` to `tests/conftest.py`.
- The existing configuration already covers the new paths: ruff (`src` and the `packages/**` and
  `tests/**` ignores), pyright (`include` and `extraPaths`), pytest (`testpaths`, `pythonpath`) and
  coverage (`source_pkgs = ["xincord.core", "xincord.plugins"]`). The layout tests check the
  namespace; each plugin's own tests check its entry point. The only change is the two ruff
  decorators above.
- Tests never unload or reload the real plugin: discord.py would re-import its modules, and later
  tests would compare against classes from the old ones.

### v3 behaved differently

- v3 behaved differently: an `option1` longer than 1024 characters overflowed the embed field, and
  the command got no reply; Discord now refuses more than 1024 characters.
- v3 behaved differently: the command failed without a reply in threads, voice channel chats and
  announcement channels (`asTextChannel()` in `Placeholder.get`); it now answers in any channel.
- v3 behaved differently: `%...%` in the options was expanded (`%bot_name%`), and an option holding
  `%_Example@option1%` made the substitution fail without a reply; option text is now inserted as
  typed.
- v3 behaved differently: the `_Example@` keys stayed in the user's cached substitutor and leaked
  into other plugins' messages; each render now uses its own values.
- v3 behaved differently: `example_key` was required but never read, and a config without it
  stopped the bot; it is optional, defaults to `example_value` and is shown in the reply.
- v3 behaved differently: the reply relied on the core's auto-defer, which
  `--no-auto-defer-interactions` turned off; the command tree now always defers this command.

## Risks / Trade-offs

- A button press re-renders the `counter` template only; an operator who moves the button into
  `example.yaml` loses the counter. The template comment says so.
- The count lives only in the button's ID: no storage, and a reloaded or restarted bot keeps
  counting from the number on the button.

## Manual smoke checklist

On a test guild, with a bot token and `plugins: [_Example]` in `config.yaml`:

1. Start the bot: the log lists `_Example` as loaded, and `plugins/_Example/config.yaml` and
   `plugins/_Example/lang/` exist.
2. `/example-command` appears with the localized names and descriptions (en-US and zh-TW clients);
   `option1` refuses more than 1024 characters.
3. `/example-command option1: hello option2: 3`: an ephemeral cyan embed shows `hello`, `3` and
   `example_value`, with v3's author, title and footer, above a `Count: 0` button.
4. Without `option2`, the second field shows `none`; with `option1: %bot_name%`, it shows
   `%bot_name%`.
5. Press the button three times: it shows `Count: 3` and the embed stays.
6. Run the command in a thread: the reply appears.
7. Set `example_key: changed`, run `/xincord reload _Example`, and run the command again: the third
   field shows `changed`; the earlier reply's button still counts.
8. Remove `_Example` from `plugins` and run `/xincord reload`: the command disappears.

## User-visible changes

New copy is in `lang/<locale>/message/example.yaml` (the field name) and
`lang/<locale>/message/counter.yaml` (the button label) of the plugin package.

1. The reply has a third embed field, `Config value` in en-US, showing `example_key`.
2. A `Count: 0` button under the reply counts presses.
3. `option1` accepts at most 1024 characters.
4. Option text is shown exactly as typed, and the command answers in threads, voice channel chats
   and announcement channels.
