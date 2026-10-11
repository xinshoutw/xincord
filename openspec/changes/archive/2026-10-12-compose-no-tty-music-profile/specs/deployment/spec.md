## MODIFIED Requirements

### Requirement: Compose service
`compose.yaml` SHALL run the `bot` service from `ghcr.io/xinshoutw/xincord`, tagged
`XINCORD_VERSION` (`latest` by default), bind-mount its own directory at `/bot` for `config.yaml`
and `plugins/`, mount the named volume `data` at `/bot/data`, run an init process without a TTY or an
open stdin, restart unless stopped, allow 30 seconds to stop, rotate its logs and start after
`lavalink` when that runs, without waiting for its health. `compose.build.yaml` SHALL build the image from a clone.

#### Scenario: Service definition
- **WHEN** `compose.yaml` is read
- **THEN** the `bot` service has those settings, no build section and no `tty` or `stdin_open`,
  depends on `lavalink` being started without requiring it, and the `data` volume is declared

#### Scenario: Building from a clone
- **WHEN** `compose.build.yaml` is read
- **THEN** it gives the `bot` service a build from the repository and the local image name

### Requirement: Lavalink service
`compose.yaml` SHALL define a `lavalink` service for MusicPlayer in the profile `music`, from an
exact `ghcr.io/lavalink-devs/lavalink` 4.x tag, 4.2.0 or later, its config inline as the compose
config `lavalink`, its password from `LAVALINK_PASSWORD` of an untracked `.env`, a healthcheck that
sends the password, restart unless stopped, rotated logs and no published port. The node config
SHALL pin its plugins, keep the HTTP, local and built-in YouTube sources off, and log no member's
query.

#### Scenario: Service definition
- **WHEN** `compose.yaml` is read
- **THEN** the `lavalink` service uses an exact 4.x tag from 4.2.0, mounts the `lavalink` config at
  `/opt/Lavalink/application.yml`, takes its password from `LAVALINK_PASSWORD`, checks its health
  with the password, restarts unless stopped, rotates its logs and publishes no port

#### Scenario: Only with the music profile
- **WHEN** `compose.yaml` and `.env.example` are read
- **THEN** the `lavalink` service is in the profile `music` only, and `.env.example` shows
  `COMPOSE_PROFILES=music` commented out

#### Scenario: Node config
- **WHEN** the `lavalink` config's content is read
- **THEN** LavaSrc has an exact release and youtube-source an exact release or a snapshot's
  40-character commit, the HTTP, local and built-in YouTube sources are off, request logging is
  off, and LavaSrc's Spotify source follows `SPOTIFY_ENABLED`, off by default

#### Scenario: No queries in the node's logs
- **WHEN** the `lavalink` config's content is read
- **THEN** request logging is off and the load handler, whose INFO lines name each identifier, logs
  warnings only

#### Scenario: Secrets stay untracked
- **WHEN** `.gitignore`, `.dockerignore` and `.env.example` are read
- **THEN** git and the build context ignore `.env`, and `.env.example` holds example values only
