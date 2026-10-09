## Why

Decision C1 ports _Example first, "rewritten as the template for the new API". v3's _Example
(`Plugins/_Example`, 5 Kotlin files, 171 lines) is the sample plugin: a config with `enabled`, a
localized guild slash command with two options, and an ephemeral embed reply with custom
placeholders. The port keeps that behavior and adds what later ports copy: a config value that is
used, a button routed through `bot.route` with its `ComponentIds`, and the conventions for a plugin
package, its bundled files and its tests.

## What Changes

- New plugin package `xincord.plugins.example`, registered in the `xincord.plugins` entry-point
  group as `_Example`, with a bundled `config.yaml` and en-US and zh-TW lang files.
- `config.yaml`: an optional `example_key` (default `example_value`) shown in the reply. v3's
  `enabled` key is gone: the core config's `plugins` list decides.
- `/example-command option1 [option2]`: a guild command localized from `register.yaml`; `option1`
  takes at most 1024 characters. The deferred ephemeral response becomes the `example` embed with
  the options and the config value, in the user's locale with a zh-TW fallback, and a counter
  button.
- The counter button (`example:1:a=count;b=<count>`) is routed to the plugin, which edits the
  message so the button shows one press more.
- Plugin test conventions: tests in `tests/plugins/<package>/`, golden data in
  `tests/fixtures/plugins/<package>/`, shared fakes in `tests/support/`, plugins loaded through
  their real entry point; the `store` fixture moves to `tests/conftest.py`.
- The port-plugin skill and the porting guide record these conventions.

Ported from:
- `XsDiscordBotKt@3a59607:Plugins/_Example/src/main/kotlin/_example/Event.kt:14-62`
- `XsDiscordBotKt@3a59607:Plugins/_Example/src/main/kotlin/_example/_Example.kt:11-43`
- `XsDiscordBotKt@3a59607:Plugins/_Example/src/main/kotlin/_example/command/Register.kt:9-33`
- `XsDiscordBotKt@3a59607:Plugins/_Example/src/main/kotlin/_example/command/CmdFileSerializer.kt:6-22`
- `XsDiscordBotKt@3a59607:Plugins/_Example/src/main/kotlin/_example/config/ConfigSerializer.kt:6-12`
- `XsDiscordBotKt@3a59607:Plugins/_Example/src/main/resources/config.yaml:1-2` and the lang files
  under `Plugins/_Example/src/main/resources/lang/`

Out of scope: storage (v3's _Example had none), modals, listeners and background tasks, rewriting
plugin config files (only `enabled` changes, and it now only warns), and the Web Dashboard's
reload path (B13).

## Capabilities

### New Capabilities

- `plugin-example`: the _Example plugin.

### Modified Capabilities

None.

## Impact

New package `packages/xincord-plugins/src/xincord/plugins/example/` and its entry point in
`packages/xincord-plugins/pyproject.toml`; tests under `tests/plugins/example/` with helpers in
`tests/support/`. No core changes and no new dependencies.
