## Context

`Converter.convert` turns an article's HTML into Markdown: it fills `prompt`, asks the model with
the keys in turn under their rate limit, and retries a failed attempt (an error, a blank answer)
after the next of `retry-waits`, up to `max-attempts`, logging each kind of failure once per
episode. `Watcher` posts an announcement's messages (`messages.content_messages`) through the
cog's `_send` and keeps each board's posted links (`store.Posted`, v3's document); it does not keep
the posted messages' IDs. v3's prompt (140 lines) asks for fenced code blocks for code; the owner
sees fenced answers often.

## Goals / Non-Goals

**Goals:** refuse fenced answers and ask again; a reviewer's ❌ replaces a post with a reviewed
conversion; both prompts in `config.yaml`; a shorter default prompt.

**Non-Goals:** reviewing every conversion (only redone ones, as asked); feedback in Discord while a
redo runs (the log says it); a command to redo; removing the reviewer's reaction (the message goes
away); keeping redone posts in their place in the channel (the new one comes last).

## Decisions

### Refused texts are failed attempts

`Converter._attempt` refuses an answer that holds one of `reject-texts` as it refuses a blank one:
the attempt fails with `the answer holds <text>` and the kind `("refused", text)` for the failure
episodes, and the conversion waits the next of `retry-waits` before asking again. Alternative: ask
again at once, which at temperature 0.1 tends to get the same answer and spends the attempts in
seconds. A list rather than a constant: `[]` turns it off for an announcement that holds code.

### One retry loop for both prompts

`convert` and the new `review` share the loop (`_retried`): keys, rate limit, retries, refused
texts and logging; the review's lines say `review attempt` and `gave up reviewing`. A review that
gives up keeps the new conversion, with a warning: the reviewer asked for a new post.

### The posted messages in the store

`store.Announcements` keeps one entry per posted message ID in `NtustAnnouncements.posts`: the
link's board, URL and title, the channel and every message ID of the announcement, so that a ❌ on
any part finds the whole post, also after a restart. `Watcher._post` returns after recording the
IDs it posted; a store failure is a warning, never a second post. Entries are never pruned: a few a
day. Alternative: an in-memory map, lost at each restart.

### The redo

`on_raw_reaction_add` checks the user (`reviewers`), the emoji (❌ without an ID) and the store,
then runs `Watcher.redo` in a task, once per URL at a time; unloading cancels it. `redo` fetches
the article, converts it and reviews it (`_messages` with the review), posts the new messages and
records them, and only then deletes the old messages and their entries: a restart or a refused
post during the model's retries leaves the old post. A non-NTUST link or an article without
content is posted again as its title link, as a first post would be.

### The prompts

`review-prompt` gets the prompt's tokens plus `{{markdown}}`; a missing key falls back to the
bundled `config.yaml`'s value (read from the package), since a zh-TW default cannot live in a
Python file. The bundled `prompt` is replaced by a shorter one that names Discord's limits (no
tables, no images, no fences) and keeps v3's four required tokens; the review prompt asks the model
to compare the Markdown with the HTML and answer the corrected Markdown only.

## Manual check

On the owner's test guild with a working key: the first pass posts the board's first page without
fences; `reviewers: [<owner>]` and a reload; ❌ on a post: a new post comes (the log shows the
redo), and the old one goes; ❌ by another account does nothing.
