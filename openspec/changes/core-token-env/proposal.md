## Why

The bot token could be given with `--token` on the command line, where every process list of the
host shows it: v3's token leaked that way during the cutover of 2026-10-12. And with the token in
`config.yaml`, the core config is a secret as a whole, which makes it harder to back up or share.
The owner asked on 2026-10-12 for the token from the environment, and for `--token` to go.

## What Changes

- The program logs in with the environment variable `XINCORD_TOKEN` when it is set and not empty,
  or else with `token` of `config.yaml`. **Breaking**: `--token` (`-t`) is gone; the command rejects
  it with a usage message.
- Compose passes `XINCORD_TOKEN` from `.env` to the `bot` service, empty when unset;
  `.env.example` shows it. The default `config.yaml`, the README and the porting guide say so.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `core-runtime`: the command line options (no `--token`) and the token's sources at startup.
- `deployment`: the bot service's token from `.env`.

## Impact

`xincord.core.cli`, the default `config.yaml`, `compose.yaml`, `.env.example`, README,
`docs/porting-guide.md`, `docs/architecture.md`, `docs/porting/decisions.md` (Amendment 7),
`tests/core/test_cli.py`, `tests/core/test_startup.py`, `tests/test_container.py`. An operator who
passes `--token` sets `XINCORD_TOKEN` or `token` instead.
