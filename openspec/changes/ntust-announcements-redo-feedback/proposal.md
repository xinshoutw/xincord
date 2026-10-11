## Why

On 2026-10-12, after trying the reviewers' cross mark on the test guild, the owner asked for a sign
that the bot took the mark: a redo takes about a minute (a conversion and a review), and until the
new post replaces the old one nothing in Discord shows that it runs.

## What Changes

- When the plugin takes a reviewer's ❌ for a redo, it adds ⏳ (HOURGLASS WITH FLOWING SAND, U+23F3)
  to the marked message. The message goes away with the old post when the redo replaces it; when
  the old post stays (the article or the new post failed, or the redo raised), the plugin removes
  its ⏳.
- A reaction that Discord refuses (no Add Reactions permission) is a warning; the redo goes on.
- `Watcher.redo` returns whether it replaced the post.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `plugin-ntust-announcements`: a redo shows that it runs (one requirement added).

## Impact

`packages/xincord-plugins/src/xincord/plugins/ntust_announcements/` (`cog.py`, `watch.py`) and
its tests. The bot needs Add Reactions and Read Message History in the boards' channels for the
sign; without them the redo works unsigned.
