## MODIFIED Requirements

### Requirement: Lavalink service
`compose.yaml` SHALL define a `lavalink` service for MusicPlayer from an exact
`ghcr.io/lavalink-devs/lavalink` 4.x tag, 4.2.0 or later (Ubuntu, arm64, DAVE), with
`lavalink/application.yml` mounted read-only, its password from `LAVALINK_PASSWORD` of an untracked
`.env`, a healthcheck that sends the password, restart unless stopped, rotated logs and no
published port. The node config SHALL pin its plugins, keep the HTTP, local and built-in YouTube
sources off, and log no member's query.

#### Scenario: Service definition
- **WHEN** `compose.yaml` is read
- **THEN** the `lavalink` service uses an exact 4.x tag from 4.2.0, mounts the config read-only,
  takes its password from `LAVALINK_PASSWORD`, checks its health with the password, restarts unless
  stopped, rotates its logs and publishes no port

#### Scenario: Node config
- **WHEN** `lavalink/application.yml` is read
- **THEN** LavaSrc has an exact release and youtube-source an exact release or a snapshot's
  40-character commit, the HTTP, local and built-in YouTube sources are off, request logging is
  off, and LavaSrc's Spotify source follows `SPOTIFY_ENABLED`, off by default

#### Scenario: No queries in the node's logs
- **WHEN** `lavalink/application.yml` is read
- **THEN** request logging is off and the load handler, whose INFO lines name each identifier, logs
  warnings only

#### Scenario: Secrets stay untracked
- **WHEN** `.gitignore`, `.dockerignore` and `.env.example` are read
- **THEN** git and the build context ignore `.env`, and `.env.example` holds example values only

## ADDED Requirements

### Requirement: Remote cipher for the node
The node SHALL send youtube-source's signature work to the remote cipher server at
`YOUTUBE_CIPHER_URL`, by default the public `https://cipher.kikkia.dev/`, with the password
`YOUTUBE_CIPHER_PASSWORD`, empty by default, which compose passes from `.env`. `.env.example` SHALL
show both commented.

#### Scenario: Node config and compose
- **WHEN** `lavalink/application.yml` and `compose.yaml` are read
- **THEN** youtube-source's `remoteCipher` takes its URL and password from the two variables, with
  those defaults, and the `lavalink` service passes both from `.env`

#### Scenario: Example
- **WHEN** `.env.example` is read
- **THEN** it holds `YOUTUBE_CIPHER_URL` and `YOUTUBE_CIPHER_PASSWORD` as comments only
