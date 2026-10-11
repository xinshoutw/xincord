## Why

On 2026-10-11 the owner's `/xincord reload` in the test guild stayed "thinking" for over a minute.
Every reload uploads the global commands and every guild's commands with force (`core-reload`),
Discord allows about two uploads a minute per route, and the reply waits for the uploads; a guild
join and a plugin reload just before had used the routes up. The owner chose that a reload uploads
only what changed and that a restart repairs the commands instead. The same run showed the error
for missing intents saying "needs the members intents" for a single intent.

## What Changes

- A reload uploads only the scopes whose commands changed since their last upload, as READY does:
  a reload that changes no command uploads nothing and answers within seconds. A failed reload
  that unloaded plugins uploads the scopes that lost their commands.
- The first READY after the program starts uploads every scope with force, so that a restart
  repairs commands that another program with the same application (v3, for one) overwrote. Later
  READYs (new sessions after a reconnect) upload only what changed, as before.
- Joining a guild still uploads its commands with force.
- The error for a plugin that needs intents the bot lacks says `intent` for one and `intents` for
  several.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `core-runtime`: the first READY uploads with force and reloads upload only changes (two
  requirements modified).

## Impact

`src/xincord/core/bot.py` and its tests. No config, data or dependency change. Operators who
relied on a reload to repair the commands restart the bot instead.
