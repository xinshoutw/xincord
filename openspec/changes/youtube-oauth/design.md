## Context

youtube-source 1.18.2 plays with MUSIC (search only), ANDROID_VR, WEB and WEBEMBEDDED by default;
only its TV client uses an OAuth account. With `oauth.enabled`, the plugin logs an address and a code
for a device login at its start; once an account is linked, it logs the refresh token, which a
later start takes from `oauth.refreshToken` instead of asking again.

## Decisions

### The account's client last

The clients are the defaults in their order, then TV: videos that play without the account keep
playing as before, and only those the others fail reach TV. Alternative: TV first (every playback on
the account, which YouTube may then limit).

### Settings from .env

`oauth.enabled: ${YOUTUBE_OAUTH_ENABLED:false}` and `oauth.refreshToken: ${YOUTUBE_OAUTH_REFRESH_TOKEN:}`
in the node config, passed by compose from `.env` like Spotify's: the token stays untracked. The
account should be a spare one: YouTube may suspend accounts used this way.

## Manual check

On a host where a video asks for a login: `YOUTUBE_OAUTH_ENABLED=true` in `.env`, recreate the node,
open the logged address with the spare account, copy the logged refresh token into
`YOUTUBE_OAUTH_REFRESH_TOKEN`, recreate the node; the video plays.
