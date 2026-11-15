# Design

## Context

bulletin's public API (`/api/v1`) offers `GET /events?after=<id>&limit=<1-500>`: events in ID
order (`published`, `revised`, `withdrawn`, `restored`, `rendered`), each with `notify`, `late`,
`at` and the announcement as the stream lists it (`id`, `url`, `link_item`, `title`, `boards`
such as `1053-1436`, `rendition` summary). `GET /announcements/{id}` adds the rewrite's Markdown
(`rendition.markdown`, at most 4,096 UTF-16 units, checked for Discord) and `attachments`
(`name`, `url`). A `published` event is notify-worthy only for a first publication: backfills,
late discoveries and cross-posts are not. bulletin renders first publications before its backlog,
but its Gemini quota can run out for hours.

bulletin polls boards by tier (P1 every 5 to 20 minutes up to P4 daily; some boards off). The
owner decided on 2026-11-15 that the plugin follows bulletin's timing, not the scraper's hourly
passes.

## Goals / Non-Goals

**Goals:**

- Post each new announcement of a configured board or site once per channel, with bulletin's
  rewrite when it comes in time.
- Survive restarts without reposting or losing waiting announcements.
- Keep the message format: the header, the title link, Markdown split at its structure.

**Non-Goals:**

- Editing or deleting posts after revisions or withdrawals.
- Posting cross-posts and backfills, which bulletin marks as not notify-worthy.
- Changing bulletin's tiers or rewriting.

## Decisions

1. **The events feed, not the stream.** The feed has a cursor and a notify flag; the stream
   would need dates and deduplication. Each pass reads `events?after=<position>&limit=500` until
   a page holds fewer than 500.
2. **Wait for the rewrite, up to `rendition-wait` (3600 s by default).** Posting at once would
   post title links during every quota gap. Editing a post when the rewrite arrives would mean
   edits that notify nobody and parts out of order. The wait is counted from the event's `at`, so
   a restart keeps it. A `rendered` event makes a waiting announcement due at once. Link entries
   are never rendered and post at once.
3. **Channels are chosen when posting.** The announcement is read again from
   `/announcements/{id}` when due, and its boards then decide the channels. A cross-post that
   arrives while the original waits adds its board's channel.
4. **One state document**: namespace `NtustAnnouncements.feed`, key `state`,
   `{"after": int, "waiting": [{"id": int, "due": ISO-8601, "posted": [channel IDs]}]}`. It is
   saved after each page of events and after each post. The in-memory copy is the truth while
   the plugin runs, so a refused write never reposts before a restart. A post is sent, then
   saved: a crash between the two reposts once rather than losing a post.
5. **The first read starts at the end.** With no document, the plugin reads the whole feed
   without posting (about six requests today) and stores the last ID. Nothing old is posted, and
   the old per-board documents are not converted.
6. **Retry, then give up.** A failed announcement read or a refused first message keeps the entry
   for the next pass. An entry still waiting a day after it was due is dropped with an error, so
   a deleted channel cannot pin an entry forever. A 404 drops it at once. A refused later part
   counts as posted, as before.
7. **`<site>` keys and channel 0.** A `board` of `1053` matches every board of site 1053. Channel
   0 marks a board without a channel yet: it is skipped, and one info line at READY lists such
   boards. The plugin loads with the bundled file. With no channel at all, the loop does not
   start.
8. **The public URL by default.** `https://bulletin.ntust.org/api/v1` goes through Cloudflare,
   whose cache keeps a page for up to 60 s. That is within one `poll-interval`. On the host,
   `api-url` can point at `http://bulletin-internal:8000/api/v1` if the bot joins `proxy-net`.
9. **Validated answers.** API answers are parsed with pydantic models that keep only the fields
   used. Anything else is an "unexpected answer" failure, logged and retried.
10. **Modules.** `bulletin.py` (the HTTP client and its models) replaces `web.py`, `api.py`,
    `conversion.py`, `pages.py` and `markup.py`. `feed.py` holds the loop's logic, replacing
    `watch.py`. `store.py` holds the state document. `messages.py` gains the rewrite's messages.

## User-visible changes (for the owner's review)

- Post text comes from bulletin's rewrite: the header, `# [title](url)` with the school's title,
  a blank line, the rewrite, and a list of `- [name](url)` attachment lines. Before, the
  plugin's own prompt wrote the whole post, attachments included.
- An announcement whose rewrite is not ready within an hour is posted as its title link only.
- Timing follows bulletin's tier for each board, daily for P4 boards. LANGUAGE_CENTER_EXTERNAL
  (`1070-1829`) is off in bulletin and posts nothing until bulletin polls it.
- The reviewers' cross mark redo and its hourglass are gone.
- A newly configured board posts nothing old. Before, it posted its whole first page.
- Cross-posts from other sites are not posted, unless one arrives while its original waits.
- New config keys: `api-url`, `poll-interval`, `rendition-wait`, `boards[].board`, and channel 0
  as a placeholder. The scraper's keys only warn.

## Risks / Trade-offs

- bulletin is a single point of failure. While it is down, posts wait; the position keeps them
  for later.
- Notify-worthy events had not yet been seen in production when this was written: bulletin
  started on 2026-11-15, a Sunday. The first weekday shows whether detection marks new
  announcements as expected.
- The old documents (`NtustAnnouncements` and `NtustAnnouncements.posts`) stay in the store.
  Rolling back to the scraper would repost what it missed in the meantime.
