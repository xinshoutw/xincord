## Context

youtube-source 1.18.2 (2026-07-27) is the latest release. Its master holds unreleased fixes,
among them a PlayStation 4 User-Agent for the TV client (#233), and Lavalink's snapshot repository
publishes each commit as `dev.lavalink.youtube:youtube-plugin:<commit>`, which the node downloads
with `snapshot: true`. The plugin's local signature cipher fails on current player scripts; its
`remoteCipher` setting sends that work to a yt-cipher server (kikkia/yt-cipher), whose author runs
a public instance without a password.

## Decisions

### A snapshot pinned by commit

The commit pins the plugin as exactly as a release. Renovate's Maven manager looks versions up in
the releases repository, which knows no commits: a rule disables updates while the pin is a
40-character commit, and the review queue says to move back to a release that holds #233.

### The public cipher by default

Without a remote cipher the plugin's own one fails, so the default is the public instance; an
operator sets `YOUTUBE_CIPHER_URL` (and `YOUTUBE_CIPHER_PASSWORD`) for a server of their own, such
as yt-cipher's container on compose's network. Alternative: a yt-cipher service in `compose.yaml`
(one more image to keep current, for a request that carries no member data).

## Manual check

Done on the production host on 2026-10-12: with the snapshot, the OAuth account and the public
cipher, an official music video that every client had failed played to the owner.
