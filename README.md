# xincord

xincord is a modular Discord bot built on [discord.py](https://github.com/Rapptz/discord.py): a
small core loads plugins through entry points and gives them YAML config, SQLite storage, i18n,
message templates and component IDs that survive restarts.

Status: 1.x, running the owner's bots since 2026-10-12. The plugin API (`docs/plugin-api.md`)
follows semver.

The bundled plugins: AutoRole, BotInfo, Calculator, ChatLogger, CustomCommands,
DynamicVoiceChannel, Economy, Example, Feedback, Giveaway, MusicPlayer (with a Lavalink node),
NtustAnnouncements, NtustCourseWatch, Ticket, TicketAwayNotice, UptimeHeartbeat, VoiceLogger and
WelcomeGoodbye.

## Packages

| Distribution | Import package | Contents |
|---|---|---|
| `xincord` | `xincord.core` | the plugin host, storage, i18n and message templates |
| `xincord-plugins` | `xincord.plugins` | the official plugins |

## Running

```sh
uv tool install xincord --with xincord-plugins   # or: pip install xincord-plugins
xincord --help
xincord
```

In a clone, `uv run xincord` runs the workspace's code.

xincord works in the current directory: it writes `config.yaml` on the first start, keeps each
plugin's files in `plugins/<Name>/`, its database in `data/xincord.db`, and the data files that a
plugin keeps itself in `data/<Name>/` (ChatLogger's message log). Set the bot token in the
environment variable `XINCORD_TOKEN` (or `token` in `config.yaml`) and list the plugins to load
under `plugins`. `--no-online` loads the config and the
plugins without connecting and exits with status 1 if one did not load. SIGINT or SIGTERM stops
the bot; SIGHUP, or `/xincord reload [plugin]` run by the application owner, reloads the config
and the plugins without disconnecting. In a terminal, the `console > ` prompt accepts
`reload [plugin]` and `stop` (or `exit`, `shutdown`, ^D).

## Docker

No clone needed: an empty directory with `compose.yaml` and `.env` runs the published image, and the
bot keeps `config.yaml` and `plugins/` next to them.

```sh
curl -fsSLO https://raw.githubusercontent.com/xinshoutw/xincord/main/compose.yaml
curl -fsSL -o .env https://raw.githubusercontent.com/xinshoutw/xincord/main/.env.example
# in .env: XINCORD_TOKEN, LAVALINK_PASSWORD, and XINCORD_VERSION, TZ, COMPOSE_PROFILES=music (MusicPlayer's
# node), Spotify or YouTube's settings if wanted
docker compose up -d             # start; the bot writes config.yaml and plugins/ on the first start
docker compose kill -s HUP bot   # reload the config and the plugins
docker compose logs -f bot       # logs, rotated at 10 MB
docker compose exec -T bot python -m xincord.core.backup   # back up data/ into backups/
docker compose pull              # update to XINCORD_VERSION, then docker compose up -d
docker compose stop              # stop
```

The image runs `xincord` as a non-root user; the database stays in the `<directory>_data` volume
(the empty `data/` beside `compose.yaml` is only its mount point). The backup command copies it
while the bot runs into `backups/<UTC time>/` beside `compose.yaml` and keeps the newest 7
(`--keep`): run it daily from cron or launchd, and copy `backups/` off the host.
The `lavalink` service plays MusicPlayer's audio with the config inline in `compose.yaml`; it runs
when `.env` sets `COMPOSE_PROFILES=music`. Its password is `LAVALINK_PASSWORD` in `.env`, and `lavalink.password` in
`plugins/MusicPlayer/config.yaml` is the same. Videos that YouTube plays only to a signed-in client
need its OAuth on a spare Google account; YouTube's signatures are solved by a remote yt-cipher
server, the public one by default (`.env.example`). In a clone, `docker compose -f compose.yaml -f
compose.build.yaml up -d --build` builds the image instead of pulling it.

## Development

Requires [uv](https://docs.astral.sh/uv/) and Node.js 20.19 or newer (for OpenSpec).

```sh
uv sync
uv run prek install
scripts/gate.sh
```

Specifications live in `openspec/`; project rules for contributors and coding agents are in
`AGENTS.md`. `docs/` holds the architecture, the decisions, the plugin conventions, the plugin API
and the pitfalls. Renovate opens version updates and Dependabot security updates
(`.github/renovate.json`, `.github/dependabot.yml`).

## Releasing

A GPG-signed `v*` tag releases xincord:

```sh
# Set the same version in pyproject.toml and packages/xincord-plugins/pyproject.toml, and in
# the latter's requirement xincord==<version>.
uv lock
git commit -S -am "build: release 0.2.0"
git push origin main
git tag -s v0.2.0 -m "xincord 0.2.0"
git push origin v0.2.0
```

The `release` workflow checks the tag's signature and the versions, builds both distributions and
the `linux/amd64` and `linux/arm64` image `ghcr.io/xinshoutw/xincord`, and creates the GitHub
Release (a prerelease while the version is 0.x). PyPI publishing starts at 1.0.0: `xincord`, then
`xincord-plugins`, each in its own environment (`pypi`, `pypi-plugins`) that waits for your
approval. Running the workflow by hand is a dry run that pushes and publishes nothing.

## License

xincord is licensed under the GNU Affero General Public License, version 3 or later
(`AGPL-3.0-or-later`).
