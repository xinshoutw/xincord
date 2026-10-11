## ADDED Requirements

### Requirement: YouTube OAuth for the node
The node SHALL list youtube-source's default clients and then TV, the client that uses an OAuth
account, and take `oauth.enabled` and `oauth.refreshToken` from `YOUTUBE_OAUTH_ENABLED` (false by
default) and `YOUTUBE_OAUTH_REFRESH_TOKEN` (empty by default), which compose passes from `.env`.
`.env.example` SHALL show both commented.

#### Scenario: Compose passes the settings
- **WHEN** `compose.yaml` is read
- **THEN** the `lavalink` service sets `YOUTUBE_OAUTH_ENABLED` to `${YOUTUBE_OAUTH_ENABLED:-false}`
  and `YOUTUBE_OAUTH_REFRESH_TOKEN` to `${YOUTUBE_OAUTH_REFRESH_TOKEN:-}`

#### Scenario: Node config
- **WHEN** `lavalink/application.yml` is read
- **THEN** youtube-source's clients are MUSIC, ANDROID_VR, WEB, WEBEMBEDDED and TV in that order,
  and its OAuth settings follow the two variables

#### Scenario: Example
- **WHEN** `.env.example` is read
- **THEN** it holds `YOUTUBE_OAUTH_ENABLED` and `YOUTUBE_OAUTH_REFRESH_TOKEN` as comments only
