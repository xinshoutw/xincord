# xincord

xincord is a modular Discord bot built on [discord.py](https://github.com/Rapptz/discord.py). It is
a Python port of [XsDiscordBotKt](https://github.com/xinshoutw/XsDiscordBotKt) (Kotlin, JDA).

Status: in development (0.x). The port follows `docs/porting/decisions.md`; the Kotlin bot stays in
service until every in-scope plugin passes its scenarios.

## Packages

| Distribution | Import package | Contents |
|---|---|---|
| `xincord` | `xincord.core` | the plugin host, storage, i18n and message templates |
| `xincord-plugins` | `xincord.plugins` | the official plugins |

## Running

```sh
uv run xincord --help
uv run xincord --token "<bot token>"
```

xincord works in the current directory: it writes `config.yaml` on the first start, keeps each
plugin's files in `plugins/<Name>/`, its database in `data/xincord.db`, and the data files that a
plugin keeps itself in `data/<Name>/` (ChatLogger's message log). Set `token` (or pass
`--token`) and list the plugins to load under `plugins`. `--no-online` loads the config and the
plugins without connecting and exits with status 1 if one did not load. SIGINT or SIGTERM stops
the bot; SIGHUP, or `/xincord reload [plugin]` run by the application owner, reloads the config
and the plugins without disconnecting. In a terminal, the `console > ` prompt accepts
`reload [plugin]` and `stop` (or `exit`, `shutdown`, ^D).

## Docker

```sh
cp .env.example .env             # once: set LAVALINK_PASSWORD (and Spotify, if wanted)
docker compose up -d --build     # start; the bot writes bot/config.yaml on the first start
docker compose attach bot        # the console (Ctrl-P Ctrl-Q detaches)
docker compose kill -s HUP bot   # reload the config and the plugins
docker compose logs -f bot       # logs, rotated at 10 MB
docker compose stop              # stop
```

The image runs `xincord` as a non-root user. `./bot` holds `config.yaml` and `plugins/<Name>/`
for editing on the host; the database stays in the `xincord_data` volume. The `lavalink` service
plays MusicPlayer's audio (`lavalink/application.yml`); its password is `LAVALINK_PASSWORD` in
`.env`, and `lavalink.password` in `bot/plugins/MusicPlayer/config.yaml` is the same.

## Development

Requires [uv](https://docs.astral.sh/uv/) and Node.js 20.19 or newer (for OpenSpec).

```sh
uv sync
uv run prek install
scripts/gate.sh
```

Specifications live in `openspec/`; project rules for contributors and coding agents are in
`AGENTS.md`. Renovate opens version updates and Dependabot security updates
(`.github/renovate.json`, `.github/dependabot.yml`).

## License

xincord is licensed under the GNU Affero General Public License v3 (AGPLv3).
