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
plugin's files in `plugins/<Name>/` and its database in `data/xincord.db`. Set `token` (or pass
`--token`) and list the plugins to load under `plugins`. `--no-online` loads the config and the
plugins without connecting and exits with status 1 if one did not load. SIGINT or SIGTERM stops
the bot.

## Development

Requires [uv](https://docs.astral.sh/uv/) and Node.js 20.19 or newer (for OpenSpec).

```sh
uv sync
uv run prek install
scripts/gate.sh
```

Specifications live in `openspec/`; project rules for contributors and coding agents are in
`AGENTS.md`.

## License

xincord is licensed under the GNU Affero General Public License v3 (AGPLv3).
