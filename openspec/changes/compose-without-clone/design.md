## Decisions

### The directory of compose.yaml is /bot

`.:/bot` bind-mounts the whole directory: the bot writes `config.yaml` and `plugins/` there on its
first start, as it did in `./bot`. A mount per file would need `config.yaml` to exist beforehand
(Docker creates a directory for a missing source). The container also sees `compose.yaml` and
`.env`, which it does not read. The database stays in the named volume (B16, the owner's answer of
2026-10-12): SQLite on a macOS bind mount goes through the VM's file sharing.

### The published image

`ghcr.io/xinshoutw/xincord:${XINCORD_VERSION:-latest}` (the owner's choice of 2026-10-12): an
operator pins a release in `.env`; without it, `docker compose pull` follows the newest. A build
section in `compose.yaml` would make compose build instead of pulling, so the build lives in
`compose.build.yaml`, which a clone adds with `-f`.

### The node's config inline

Compose's `configs` with `content` (Compose 2.23.1 and later) holds `application.yml`, mounted at
`/opt/Lavalink/application.yml`. Compose interpolates `${VAR:-default}` in it from `.env`, so the
Spring placeholders and their environment variables go: the values arrive as written. A literal `$`
in the node's config would need `$$`. The password stays an environment variable, which the
healthcheck reads.

## Migration

Per deployment: stop it, move `bot/config.yaml` and `bot/plugins/` into the directory of
`compose.yaml`, replace `compose.yaml` (and keep `.env`, adding `XINCORD_VERSION`), start it. The
volume `<directory>_data` keeps its name while the directory keeps its name.

## Manual check

In an empty directory with only `compose.yaml` and `.env`: `docker compose up -d` pulls both
images, the bot writes `config.yaml` and `plugins/` next to them, and the node starts with its
inline config (its log names the plugins, the clients and the remote cipher).
