## Why

Running xincord took a clone of the repository: compose built the image from it and kept the bot's
files in `./bot` and the node's config in `lavalink/application.yml`. On 2026-10-12 the owner asked
that operators need only the basics, without a clone, and that the directory of `compose.yaml` be
the bot's own, with `config.yaml` and `plugins/` in it and no `bot/` level.

## What Changes

- `compose.yaml` runs the published image `ghcr.io/xinshoutw/xincord`, tagged `XINCORD_VERSION` from
  `.env` (`latest` by default), and bind-mounts its own directory at `/bot`: `config.yaml` and
  `plugins/` sit next to `compose.yaml` and `.env`. The database stays in the named volume `data`
  (decision B16). **Breaking for existing deployments**: move `bot/config.yaml` and `bot/plugins/`
  up one level.
- The Lavalink node's config moves into `compose.yaml` (compose `configs`, inline content), which
  compose fills in from `.env`; `lavalink/application.yml` is gone. An operator downloads
  `compose.yaml` and `.env.example`, nothing else.
- `compose.build.yaml` builds the image from a clone instead (`docker compose -f compose.yaml -f
  compose.build.yaml up -d --build`), for development.
- Renovate's Maven manager reads the node's plugins in `compose.yaml`, and leaves the xincord image
  alone.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `deployment`: the container image's build context, the compose service, the Lavalink service, the
  node's YouTube OAuth and remote cipher.
- `project-tooling`: Renovate's managers for the node's plugins and the xincord image.

## Impact

`compose.yaml`, new `compose.build.yaml`, `lavalink/application.yml` (removed), `.dockerignore`,
`.gitignore`, `.env.example`, README, `.github/renovate.json`, `tests/test_container.py`,
`tests/test_dependency_updates.py`. Deployments move their files up one level; the volume keeps its
name while the directory does.
