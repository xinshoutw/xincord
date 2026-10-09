## Context

v3 has no central routing: each plugin's listener receives every interaction event and filters
with `checkComponentIdPrefix` / `checkModalIdPrefix` (`GlobalUtil.kt:52-62`). Template views in
xincord are stopped, so discord.py never dispatches them; an interaction that no live view handles
is only announced through the `interaction` event.

## Goals / Non-Goals

**Goals:** one router for components and modals that knows each plugin's codec, error isolation,
and the lazy upgrade of legacy IDs (B9).

**Non-Goals:** application commands (discord.py's tree); interaction placeholder keys.

## Decisions

- **Registration.** `bot.route(__name__, ids, handler)` from the plugin's `setup`; the handler is
  `async (interaction, ParsedId) -> None`. Routes are stored per plugin name and checked in
  registration order; the first codec that owns the ID wins.
- **Dispatch.** The bot's `on_interaction` handles `component` and `modal_submit` interactions;
  the custom ID comes from `interaction.data`. Handler exceptions are logged and do not reach the
  upgrade step.
- **Lifecycle.** `reload_plugin` clears a plugin's routes before `reload_extension`; whichever
  `setup` then runs (the new one, or the old one that discord.py restores after a failure)
  registers them again. A failed load clears the routes its setup registered before failing.
- **Upgrade.** The handler may already have edited the message, so the bot fetches it again
  instead of trusting `interaction.message`. `View.from_message` (or `LayoutView.from_message` for
  Components V2 messages) rebuilds the components, `upgrade_view` rewrites them with every
  registered codec, and the view is stopped before `message.edit` so discord.py does not dispatch
  it. Ephemeral messages are skipped: they cannot be fetched through the channel.

### v3 behaved differently

- v3 behaved differently: every plugin received every component and modal event and filtered by
  prefix; now only the owning plugin's handler runs.

## Risks / Trade-offs

- The upgrade costs one fetch per legacy interaction; each message is upgraded once.

## User-visible changes

None. Old buttons keep working; their message is edited silently after the first use.
