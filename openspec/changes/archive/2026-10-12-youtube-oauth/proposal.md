## Why

On the production host, YouTube asks youtube-source's default clients to sign in for some official
music videos ("This video requires login" from ANDROID_VR, "This video is unavailable" from
WEBEMBEDDED), while other videos play (checked on 2026-10-12). youtube-source plays such videos
through its TV client with an OAuth account. The owner chose OAuth on a spare Google account.

## What Changes

- `lavalink/application.yml` lists youtube-source's default clients (MUSIC, ANDROID_VR, WEB,
  WEBEMBEDDED) and then TV, the client that uses the account, and takes `oauth.enabled` and
  `oauth.refreshToken` from `YOUTUBE_OAUTH_ENABLED` (false by default) and
  `YOUTUBE_OAUTH_REFRESH_TOKEN` (empty).
- `compose.yaml` passes both from `.env` to the `lavalink` service; `.env.example` shows them
  commented, with the steps; README says where.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `deployment`: one requirement added for the node's YouTube OAuth.

## Impact

`compose.yaml`, `lavalink/application.yml`, `.env.example`, `README.md`, `tests/test_container.py`.
No code change. Without the two settings nothing changes but the explicit client list.
