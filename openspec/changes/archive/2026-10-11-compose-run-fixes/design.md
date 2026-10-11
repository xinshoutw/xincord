## Context

Step 3 of the `container` change's manual check needs a real token, so it waited for the owner. On
2026-10-11 the owner created a test application and guild and put its token in `bot/config.yaml`;
Claude ran the rest on the owner's Mac (OrbStack, compose): the bot logged in (`Bot ready`), the
database is in the `xincord_data` volume, the console's `reload` worked and Ctrl-P Ctrl-Q detached,
SIGHUP reloaded, `docker compose stop` took 0.3 s with exit status 0, and Lavalink turned healthy.

What the run showed:

- Six reloads (one from the console, five SIGHUPs) logged their summaries at 14:26:52, 14:27:53,
  14:28:52, 14:28:54, 14:29:53 and 14:30:53: after the first, about one a minute. Each reload holds
  `Bot._reloading` while it uploads the global and every guild's commands with force
  (`core-reload`), discord.py sleeps before a request when the route's bucket is empty and logs that
  at DEBUG only, and the summary was logged after the upload.
- prompt_toolkit's default completion menu keeps `reserve_space_for_menu` (8) lines below the
  prompt whenever a completer is set and completion while typing is on. Rendered on a pty, every
  redraw printed `\r\r\n` seven times and `ESC[7A`; with `CompleteStyle.READLINE_LIKE` it printed
  neither, only moves within the prompt's line. The container's terminal output is what `docker
  compose logs` shows.
- prompt_toolkit asks the terminal for the cursor position (`ESC[6n`); with no terminal attached it
  prints `WARNING: your terminal doesn't support cursor position requests (CPR).`
- discord.py's `Client.__init__` logs the voice warnings when `VoiceClient.warn_nacl` or
  `warn_dave` is set. Only MusicPlayer joins voice, with `channel.connect(cls=link.voice)`, a
  `VoiceProtocol` that Lavalink drives; discord.py's own `VoiceClient` is never used.

## Goals / Non-Goals

**Goals:** the summary of a reload appears when its plugins are done; a queued reload says so; a
readable `docker compose logs`; no misleading warnings at startup.

**Non-Goals:** fewer or unforced uploads (the forced upload is `core-reload`'s decision: a reload
also repairs the commands on Discord); logging discord.py's rate-limit waits; another console
library; running the console without a TTY.

## Decisions

### The summary before the upload

`Bot.reload` logs the summary right after the plugins are reloaded and before
`_sync_commands(force=True)`, still inside the lock, and returns it after the upload, so
`/xincord reload` replies once the commands are on Discord. A failed reload already logs its error
before the upload. Alternative: log only after the upload, as before (the delay this change
removes).

### Saying that a reload waits

`Bot.reload` logs `Waiting for the running reload to finish` when the lock is held as it starts.
Alternative: nothing, as before: a SIGHUP sent while another reload uploads looked lost.

### readline-like completion

`PromptSession(complete_style=CompleteStyle.READLINE_LIKE)`: Tab completes a single match in place
and lists several above the prompt, as bash does. No lines are kept free below the prompt, so log
lines printed above it come out as plain lines. Alternative: `reserve_space_for_menu=0` with the
menu kept, which would draw the menu over the lines below the prompt.

### No CPR in the image

`ENV PROMPT_TOOLKIT_NO_CPR=1` in the Dockerfile. In a terminal (`uv run xincord`) the request is
answered, so only the image sets it. With readline-like completion the prompt needs no cursor row.

### Voice warnings off

`Bot.__init__` sets `discord.VoiceClient.warn_nacl` and `warn_dave` to false before
`commands.Bot.__init__`. A plugin that used discord.py's own voice without PyNaCl would still fail
at connect, with discord.py's error.

## Manual check

1. `docker compose up -d --build`; `docker compose logs bot` shows no voice warning and no CPR
   warning, and no blank lines between the log lines.
2. `docker compose kill -s HUP bot` twice in a row: the first summary appears at once, the second
   reload logs that it waits, then its summary.
3. `docker compose attach bot`: Tab after `re` completes `reload`; Ctrl-P Ctrl-Q detaches.

Result on 2026-10-11 (OrbStack, the owner's test application): the log after `up -d --build` has
no voice or CPR warning, no blank line and no cursor move up; two SIGHUPs in a row logged the
first summary at once, then `Waiting for the running reload to finish` and the second summary;
in the attached console, `re` and Tab completed `reload`, and a reload typed while another
uploaded logged that it waited, then its summary 33 seconds later, when the rate limit allowed
the upload.
