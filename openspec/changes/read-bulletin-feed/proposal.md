# Proposal

## Why

NtustAnnouncements scrapes 18 NTUST boards and rewrites each article with its own Gemini keys.
The bulletin service (`bulletin.ntust.org`) now polls those boards, rewrites every new
announcement into Discord Markdown and publishes an events feed with a public API. Two scrapers
and two rewriters spend the same school bandwidth and the same Gemini quota. bulletin's decision
H2 moves this plugin to the events feed now that the feed exists.

## What Changes

- **BREAKING (config)**: the plugin reads bulletin's events feed instead of NTUST's pages.
  `config.yaml` takes `api-url`, `poll-interval`, `rendition-wait` and boards named by
  bulletin's board key (`1053-1436`). The keys for pages, layouts, the model, the prompts and the
  API keys are gone. An old file fails to load until its boards name a `board`.
- New announcements are those the feed marks notify-worthy on a configured board. Each waits
  for bulletin's rewrite, up to `rendition-wait` seconds, and is then posted: the rewrite under
  its title link, with its attachments listed, or the title link alone.
- The feed's position and the waiting announcements are stored in one document. The first read
  starts at the feed's end, so nothing old is posted.
- **BREAKING (interaction)**: the reviewers' cross mark redo, its hourglass and the stored posts
  are removed: the plugin no longer runs a model.
- Board scraping, article extraction, the model clients, the key rotation and the retries are
  removed with their tests and fixtures.

Out of scope: editing a post when the school revises an announcement, deleting one when it is
withdrawn, embeds, slash commands, and bulletin's own polling tiers and rewriting.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `plugin-ntust-announcements`: the source becomes bulletin's events feed. The config, the
  posting rule, the stored state and the logging change. Scraping, conversion and the redo are
  removed. Messages gain the rewrite's form.

## Impact

- Code: `packages/xincord-plugins/src/xincord/plugins/ntust_announcements/`. `api.py`,
  `conversion.py`, `markup.py`, `pages.py` and `web.py` are replaced by a feed client. `cog.py`,
  `config.py`, `config.yaml`, `store.py` and the posting loop change. `messages.py` gains the
  rewrite's messages.
- Tests: `tests/plugins/ntust_announcements/` and `tests/fixtures/plugins/ntust_announcements/`.
- Docs: `docs/architecture.md`, `docs/plugin-conventions.md`, `docs/pitfalls.md`,
  `docs/owner-review.md`, `README.md`.
- Shared packages stay: `ntust_tls` (NtustCourseWatch), `failures` and `redaction`.
- Deployment: the production config is rewritten for the new keys. The old per-board documents
  and stored posts stay in the store, unread.
