## Decisions

### No console under compose

The console reads `reload [plugin]` and the stop words. Under compose they have other ways in:
`/xincord reload [plugin]` (the application's owner), `docker compose kill -s HUP bot` and
`docker compose stop`. With `tty: true` the console runs in the container and prompt_toolkit's
redraws (`ESC[?2004h`, `console > `) land in the json-file log around each line, which makes the
log hard to read and to ship. Without a TTY, `main` leaves the console off (it already requires a
terminal on stdin and stdout) and discord.py's log handler writes plain lines. The console still
runs where xincord starts in a terminal (`uv run xincord`). `PROMPT_TOOLKIT_NO_CPR=1` stays in the
image for a terminal that someone gives it.

### The node in a profile

`profiles: [music]` keeps `lavalink` off unless `COMPOSE_PROFILES` (or `--profile`) names `music`;
`.env` can set it, so an operator runs the same commands either way. The bot's `depends_on` takes
`required: false` (Compose 2.20 and later; `configs.content` needs 2.23.1 already): with the
profile, the bot still starts after the node; without it, compose does not ask for the node.

`LAVALINK_SERVER_PASSWORD` keeps `${LAVALINK_PASSWORD:?...}`: compose interpolates the whole file,
the services of inactive profiles included (checked with Compose 5.1.2), so `.env` needs a password
even without the profile. `.env.example` has an example value, which an operator who copies it
keeps; the check still stops a deployment that has no `.env` at all.

The profile is off by default, as MusicPlayer is: the default core config loads no plugin.

## Migration

A deployment with MusicPlayer adds `COMPOSE_PROFILES=music` to `.env` before it takes the new
`compose.yaml`, then runs `docker compose up -d`. One without stops its node once: `docker compose
--profile music rm -sf lavalink`. Both recreate the bot without a TTY.
