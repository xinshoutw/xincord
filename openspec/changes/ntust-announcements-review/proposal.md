## Why

On 2026-10-12, while setting up NtustAnnouncements on the test guild, the owner asked for three
things: the model's answers often wrap the post in a code fence (three backticks), which should
be refused and asked again; members on a list should be able to mark a bad post with ❌ (CROSS
MARK, U+274C), which deletes it and posts a new conversion that the model checks a second time,
with a review prompt that Claude writes and that lives in `config.yaml`; and a shorter default
prompt, since current models need less instruction than v3's `gemini-2.5-flash` did. v3's prompt
itself asks for fenced code blocks, a likely source of the fences.

## What Changes

- New key `reject-texts`, a list of texts, by default three backticks: an answer that holds one of
  them is a failed attempt, retried like any other (rate limit, `max-attempts`, `retry-waits`),
  and the log names the text. `[]` refuses nothing.
- New key `reviewers`, user IDs, empty by default (off). When one of them adds ❌ to a message the
  plugin posted for an announcement, the plugin fetches the article again, converts it, has the
  model review the conversion with `review-prompt`, posts the result to the same channel, then
  deletes the old messages. Others' reactions, other emojis and a second ❌ during a redo are
  ignored; when the article cannot be fetched or the new post is refused, the old post stays.
- New key `review-prompt`, filled like `prompt` plus `{{markdown}}` (the conversion under review),
  and holding `{{html}}` and `{{markdown}}`. When it is missing, the bundled file's prompt is used,
  so existing operator files work without it.
- The plugin remembers each message it posts (the announcement, its channel and all its messages)
  in the store's namespace `NtustAnnouncements.posts`, so that a ❌ finds the announcement after a
  restart.
- Long conversions are split at their structure (the owner's request): before a heading, at a
  blank line, before a list item, at a line break, preferred in that order past half the limit,
  never right after a heading. v3 cut at the last line break that fit.
- The bundled `prompt` is a new, shorter text (owner's request); `review-prompt` is new. Both are
  zh-TW copy in `config.yaml` (owner review). Operator files keep their own prompt.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `plugin-ntust-announcements`: refused texts, remembered posts, reviewers' redo and the review
  prompt and the split of long content (five requirements added); the prompts' tokens and the
  messages (two requirements modified).

## Impact

`packages/xincord-plugins/src/xincord/plugins/ntust_announcements/` (`config.py`,
`config.yaml`, `conversion.py`, `store.py`, `watch.py`, `cog.py`, `__init__.py`) and its tests.
No new dependency or intent: reactions come with discord.py's default intents. The store gains one
entry per posted message (a few a day).
