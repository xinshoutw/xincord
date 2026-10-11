## Context

`core-reload` made every reload upload the global and every guild's commands with force, so that
a reload also repaired commands that drifted on Discord. On 2026-10-11, in the owner's test guild,
the bot joined a second guild (a forced upload of that guild), then the owner reloaded MusicPlayer
and then everything with `/xincord reload` within six seconds: each reload uploaded three scopes,
discord.py waited for Discord's rate limit (about two bulk overwrites a minute per route, waited
silently), and the full reload's reply came over a minute later. Since `compose-run-fixes` the
summary is logged before the upload, but the slash command still answers after it.

The uploads skip a scope whose payload hash equals the hash stored after its last successful
upload (`core-command-tree`), so an unforced upload sends only what changed. Commands drift from
the stored hashes only when another program overwrites them (v3 running with the same application)
or someone deletes them.

## Goals / Non-Goals

**Goals:** a reload that changes no command needs no upload; a restart repairs drifted commands;
the missing-intents error reads right.

**Non-Goals:** replying before the upload (with unforced uploads the wait is rare); a repair
command; reading the commands back from Discord to compare them; logging rate-limit waits.

## Decisions

### Reloads upload changes only

`Bot.reload` calls `_sync_commands(force=False)` after a reload, also after a failed reload that
unloaded plugins (their scopes' payloads changed, so those scopes upload). Alternative: keep the
force and reply before the upload (the owner's second option), which still queues reloads behind
the uploads.

### The first READY repairs

`Bot.on_ready` uploads with force once per process: a flag on the bot, set after the first READY's
upload. discord.py fires `on_ready` again after a new session; those upload only changes, as
before. A restart therefore repairs drifted commands, at the cost of one upload per scope at each
start, when the routes are fresh. Alternative: a repair option on `/xincord reload`, which cannot
help when the drift removed `/xincord` itself.

### Wording of the missing intents

`needs the members intent` for one flag, `needs the members, presences intents` for several. The
summary of a reload names the failed plugin only, so this shows in the log.

## Manual check

On the owner's test application and guild:

1. A full `/xincord reload` without a config change answers at once, and the commands' `version`
   on Discord (`GET /applications/<id>/commands`) stays the same.
2. A change of `plugins/CustomCommands/config.yaml` (a description) and `/xincord reload
   CustomCommands`: the guild's commands get a new `version`, the global ones keep theirs.
3. `docker compose restart bot`: every scope gets a new `version` after READY.

Result on 2026-10-11 (the owner's test application `xincord-test` in the guild `xincord-test`):
with `example-command` deleted on Discord through the API, a SIGHUP reload logged its summary
after 2.4 s and left the command deleted, and `docker compose restart bot` brought it back at
READY (40 commands). A description edited in `plugins/CustomCommands/config.yaml` reached Discord
with the next reload (summary after 2.5 s). Discord keeps a command's `version` when a bulk
overwrite sends it unchanged, so the deletion was the observable check instead of step 1's
`version`.

Found: discord.py sleeps until a bucket resets inside the request that empties it
(`Ratelimit.__aexit__` calls `_refresh`), so that request returns only after the reset although
Discord applied it at once. The reload that set the description back, 7 seconds after the edit,
waited 38 seconds for the edit's reload, whose upload had emptied the guild route's bucket. With
uploads of changes only, this happens when commands change twice within about a minute.
