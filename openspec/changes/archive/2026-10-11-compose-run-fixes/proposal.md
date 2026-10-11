## Why

The first run with a real token under compose (step 3 of the `container` change's manual check,
2026-10-11, on the owner's test application and guild) passed, but showed three things an operator
trips over:

- A reload's summary appears up to a minute late. Each reload uploads every command scope with
  force, Discord allows about two of these uploads a minute, and discord.py waits for its rate
  limit silently (DEBUG only). The summary is logged after the upload, so `docker compose kill -s
  HUP bot` looked like it did nothing; reloads sent in a row queued silently behind each other.
- `docker compose logs bot` replays the console's terminal output: after every log line the prompt
  is redrawn with seven blank lines kept free for the completion menu and a cursor move seven lines
  up, which garbles the log in a terminal; with nobody attached, the prompt's cursor position
  request goes unanswered and prompt_toolkit prints a CPR warning.
- Every start logs discord.py's warnings that PyNaCl and davey are missing ("voice will NOT be
  supported"), although voice plays through MusicPlayer's Lavalink node and never through
  discord.py.

## What Changes

- A reload logs its summary as soon as the plugins are reloaded, before the forced command upload;
  a reload that has to wait for another logs `Waiting for the running reload to finish`.
- The console lists completions above the prompt as readline does (prompt_toolkit's
  `READLINE_LIKE` style), so the prompt keeps no lines free below it and log lines add no blank
  lines.
- The image sets `PROMPT_TOOLKIT_NO_CPR=1`.
- The bot turns off discord.py's warnings about its own voice support.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `core-runtime`: the reload summary comes before the upload and a waiting reload says so; the
  console's completion style (two requirements modified); no voice warnings at startup (one
  requirement added).
- `deployment`: the image sets `PROMPT_TOOLKIT_NO_CPR=1` (one requirement added).

## Impact

`src/xincord/core/bot.py` (reload, the voice warnings), `src/xincord/core/console.py` (completion
style), `Dockerfile`, and their tests. No new dependency, no config or data change. The upload
itself is unchanged: still forced on every reload, still subject to Discord's rate limit.
