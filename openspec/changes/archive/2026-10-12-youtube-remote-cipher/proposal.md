## Why

After `youtube-oauth`, the production node still failed some official music videos: its TV client
answered "The page needs to be reloaded" (youtube-source issue #226, fixed after 1.18.2, in no
release yet), and with that fix it failed to find the signature function of YouTube's player
script, which youtube-source no longer extracts reliably: its maintainers point to a remote cipher
server (issue #240). On 2026-10-12, a snapshot of youtube-source with the fix and the public remote
cipher made such a video play on the production host, with the OAuth account.

## What Changes

- `lavalink/application.yml` pins youtube-source to the snapshot of commit `2be8e542` (the latest of
  `master`, with the TV client's fix), downloaded from Lavalink's snapshot repository, until a release
  holds the fixes.
- The node sends youtube-source's signature work to a remote cipher server: `YOUTUBE_CIPHER_URL`,
  by default the public `https://cipher.kikkia.dev/` that yt-cipher's author runs, and
  `YOUTUBE_CIPHER_PASSWORD` for a server of one's own, passed by compose from `.env`;
  `.env.example` shows both with how to run yt-cipher.
- Renovate leaves a snapshot pin alone (a rule on a 40-character commit).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `deployment`: "Lavalink service" pins youtube-source to a release or a snapshot commit; one
  requirement added for the remote cipher.
- `project-tooling`: Renovate's Maven manager leaves a snapshot commit alone.

## Impact

`lavalink/application.yml`, `compose.yaml`, `.env.example`, `README.md`, `.github/renovate.json`,
`tests/test_container.py`, `tests/test_dependency_updates.py`. Every node now reaches the remote
cipher server for YouTube's signatures: player script addresses and signatures, no member data.
