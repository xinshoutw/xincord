## Context

v3's SimpleCommand (`Plugins/SimpleCommand`, 5 Kotlin files, 209 lines) has five guild commands and
no components, listeners or storage. `Event` (`PluginEventConfigure`) exports the zh-TW lang files,
reads `config.yaml` (`enabled` only, `ConfigSerializer.kt:5-8`) and builds the command localizer
when enabled (`Event.kt:17-30`). `Register.kt:39-60` declares `cub-none-card`, `tsib-none-card`,
`ctcb-none-card`, `ctcb-remit` and `chpytwtp-remit` with the description `generate message`, the
zh-TW names and descriptions of `register.yaml` and `DefaultMemberPermissions.enabledFor(ADMINISTRATOR)`.
On any of them (`Event.kt:49-53`), `SimpleCommand.kt:21-58` queues `hook.deleteOriginal()` on the
core's ephemeral deferral (`InteractionLogger.kt:25-30`) and `channel.sendMessage(...)` with the v2
message template named after the command, rendered in the default locale zh-TW with the global
substitutor (`MessageCreator.kt:84-95`). Each template is one embed: a title, a thumbnail hot-linked
from `i.meee.com.tw`, a "third-party verification" field, for two of them a bank code field, a bank
account field, and the colour `0x9bd9d5`. The inventory is
`docs/porting/analysis/inventory/SimpleCommand.md`; its section 12 lists three issues and the data
sensitivity of the bundled account numbers.

## Goals / Non-Goals

**Goals:** v3's five commands, their text and their public messages, without v3's real account
numbers; feedback when the bot cannot post in the channel.

**Non-Goals:** a data-driven command set (commands defined in a config file); en-US or other
localizations; a runtime permission check; new commands.

## Decisions

### Package and bundled files

- `packages/xincord-plugins/src/xincord/plugins/simple_command/`: `__init__.py` (metadata and
  `setup`), `cog.py` (the commands and the posting) and `lang/`. Entry point
  `SimpleCommand = "xincord.plugins.simple_command"`.
- `INTENTS = discord.Intents.none()`: commands need no intents. `DEPENDS` and `SOFT_DEPENDS` are
  empty; `DEFAULT_LOCALE = "zh-TW"`, v3's default and only locale. No component IDs (v3 had no
  components; its unused `simplecommand@` prefix has no counterpart) and no storage.
- No `config.yaml`, and `setup` never calls `context.config`: v3's only key was `enabled`, which the
  core's `plugins` list replaces (BasicCalculator). A v3 `plugins/SimpleCommand/config.yaml` left on
  disk is ignored.
- `lang/zh-TW/register.yaml` is v3's, without its trailing blank line. The five
  `lang/zh-TW/message/*.yaml` are v3's except the bank account numbers: v3 shipped real ones inside
  the jar, and the repository never holds real account numbers, so each template has the example
  value `000000000000` under a comment that asks the operator to put theirs. No real account can be
  all zeros, so a forgotten example cannot send money to a stranger. The bank codes (`822`, `700`)
  are public institution codes and stay.
- v3's `info.yaml` keys `author`, `coreApi` and `version` have no counterpart. v3 logged
  `SimpleCommand is disabled.` when off; a plugin missing from `plugins` is never imported.
- uv_build ships every file in the package. Checked on 2026-10-10: the wheel from
  `uv build --package xincord-plugins` lists the six zh-TW lang files and the `SimpleCommand` entry
  point, and `xincord --no-online`, run from a scratch virtual environment with both wheels and
  `plugins: [SimpleCommand]`, loads the plugin, writes `register.yaml` and the five templates under
  `plugins/SimpleCommand/lang/zh-TW/`, writes no `plugins/SimpleCommand/config.yaml`, and exits
  with 0.

### Posting (`cog.py`)

`SimpleCommand.post_message(interaction)` is the callback of all five commands; v3 copied one
branch per command (inventory B2) and dispatched on `event.name`.

- The template is the one named after the invoked command (`interaction.command.name`, the base
  name), in the default locale zh-TW whatever the user's locale: v3's `getCreateBuilder(key)` used
  the default locale, and the message is public, so the invoker's locale does not choose it. An
  operator's en-US template is not used either, as in v3.
- Values: v3's global placeholders `bot_id` and `bot_name` (`Placeholder.kt:15-18`), built for this
  render only. Keys that other v3 plugins left in the shared global substitutor have no
  counterpart. The bundled templates use no placeholders.
- When `interaction.channel` takes messages (`Postable`, a `runtime_checkable` Protocol: forums and
  categories have no `send`), the plugin renders the template and sends the whole message: content,
  embeds, the view (a link button or a Components V2 layout an operator adds) and the files that
  Components V2 media with a `file_path` need, as v3 sent the whole built message. Then it deletes
  the deferred response, as v3's `deleteOriginal`.
- When the channel takes no messages or sending raises `discord.HTTPException` (missing
  permissions, for example), the plugin logs a warning that names the command and the channel,
  renders the template again and edits the deferred response into it, with the files as
  attachments. It renders again because discord.py closes a message's files once it has sent them,
  even when Discord refused the request.
- The channel is checked through a parameter typed `object`: discord.py's `send` overloads take a
  `View` or a `LayoutView`, never their union, so the Protocol states the call that the plugin
  makes.

### Commands

`SimpleCommand.command(name)` builds one command with `app_commands.Command`, as the other plugins
do: `name=lang.command(name, f"{name}.name")`, `description=lang.command("generate message",
f"{name}.description")` and `callback=self.post_message`, then
`app_commands.default_permissions(administrator=True)`, which sends `default_member_permissions` 8
as v3's `DefaultMemberPermissions.enabledFor(ADMINISTRATOR)`. They are guild commands (no
`extras["global"]`), so contexts and install types stay unset, as for BasicCalculator. `setup` adds
one command per name in `COMMANDS`, in v3's order; the core uploads them to every guild when they
change, and discord.py removes them when the plugin unloads. Without en-US lang files, en-US clients
see v3's base names and description.

### Tests

- `tests/plugins/simple_command/`: `test_plugin.py`, `test_post.py` and `test_command.py`;
  `conftest.py` loads the plugin through its entry point.
- `tests/fixtures/plugins/simple_command/golden.yaml`: v3's text, as the five embeds with the
  example account numbers and the five translated command payloads.
- The posting tests call `post_message` with a `FakeInteraction` whose `command` names the template
  and whose channel is a `FakeChannel` sharing its `sent` list.

### v3 behaved differently

- v3 behaved differently: `deleteOriginal` and `sendMessage` were queued together, so the deferred
  response was gone before the send's result was known, and a failed post (missing permissions,
  for example) left the administrator with no feedback (inventory B1); the message is now posted
  first, and when the channel refuses it, it replaces the deferred response.
- v3 behaved differently: with `--no-auto-defer-interactions`, `deleteOriginal` had no response to
  delete and the user saw "The application did not respond"; the command tree always defers these
  commands.
- v3 behaved differently: the bundled templates held real bank account numbers, shipped inside the
  jar; they hold the example value `000000000000`.
- v3 behaved differently: the messages were rendered with the shared global substitutor, which also
  held keys that other plugins had written into it; each render gets `bot_id` and `bot_name` only.

Kept on purpose: the five fixed commands (inventory B3; making them data-driven is a new feature
for the owner to decide); zh-TW for every user; zh-TW localizations only; the administrator default
permission without a runtime check, which guild administrators can change in the server's
integration settings as in v3; the third-party thumbnails and the tutorial link, which operators
change in `plugins/SimpleCommand/lang/`.

## Risks / Trade-offs

- An operator who enables the plugin on a fresh install posts the example account number until the
  templates are edited. The comment in each template says so, and the smoke checklist covers moving
  v3's lang files, which keep the real numbers because only missing lang files are exported.
- The thumbnails are hot-linked from a third-party image host, as in v3; if it removes them, the
  embeds show no thumbnail.

## Manual smoke checklist

On a test guild, with a bot token and `plugins: [SimpleCommand]` in `config.yaml`:

1. Start the bot: the log lists `SimpleCommand` as loaded; `plugins/SimpleCommand/lang/zh-TW/`
   holds `register.yaml` and the five templates, and no `plugins/SimpleCommand/config.yaml` exists.
2. As an administrator with a zh-TW client, the five commands are listed under their zh-TW names
   with the zh-TW description; with an en-US client, under v3's base names with
   `generate message`.
3. As a member without Administrator, the commands are not listed.
4. Run `/cub-none-card` in a text channel: the "thinking" message disappears and the channel gets the
   public embed with its title, thumbnail, the verification field with the tutorial link on its
   second line, the example account number and the colour #9BD9D5. Repeat for the other four;
   `ctcb-remit` and `chpytwtp-remit` also show the bank code field.
5. With an en-US client, run `/ctcb-remit`: the posted embed is the zh-TW one.
6. In a thread, the embed is posted in the thread.
7. In a channel where the bot lacks Send Messages, the embed arrives as the ephemeral response and
   the log has a warning that names the command and the channel.
8. Copy v3's `plugins/SimpleCommand/lang/` (with the real account numbers) over the bot's, run
   `/xincord reload SimpleCommand`, and check that the posted embeds show the real numbers.

## User-visible changes

Copy: the comment above the example account number in each bundled template; no other new text.

1. When the bot cannot post in the channel, the administrator sees the message as the ephemeral
   response, and the log names the channel (v3: the "thinking" message vanished and nothing was
   posted).
2. The bundled templates show the example account number `000000000000` (v3: real numbers);
   existing `plugins/SimpleCommand/lang/` files keep theirs.
3. The commands always answer (v3 needed the core's auto-defer switch).
4. No `plugins/SimpleCommand/config.yaml`: the core's `plugins` list replaces v3's `enabled`.
5. Placeholders that other plugins left in v3's global substitutor no longer expand in operator
   templates; `%bot_id%` and `%bot_name%` still do.
