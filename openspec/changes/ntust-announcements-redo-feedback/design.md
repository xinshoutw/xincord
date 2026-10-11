## Context

`NtustAnnouncements.on_raw_reaction_add` takes a reviewer's ❌ on a stored message and runs
`Watcher.redo` in a task: a new conversion, the model's review, the new post, then the old
messages' deletion. It takes about a minute with `gemini-3.8-flash`; the reviewer sees nothing
until the old post disappears.

## Goals / Non-Goals

**Goals:** an immediate sign on the marked message; no sign left behind on a post that stays.

**Non-Goals:** signs on the other parts of the post; a sign for ignored marks; removing the
reviewer's ❌ (it goes with the message).

## Decisions

### ⏳ from the redo's task

`_redo` adds ⏳ to the marked message through a partial message (no fetch, no cache) before the
redo starts, so the listener returns at once. `Watcher.redo` returns whether it replaced the post;
when it did not, or when it raised, `_redo` removes the bot's ⏳ (`remove_reaction` with the bot's
user). A refused reaction or removal is a warning that names the message; the redo goes on.
Alternative: ✅ when done, which the deletion of the old post would remove anyway.

### Which hourglass

⏳ (U+23F3, flowing sand) reads as "in progress"; ⌛ (U+231B) as "time is up".

## Manual check

On the test guild: ❌ on a post shows ⏳ on that message within a second; about a minute later the
post is replaced. With the article page failing (or a refused new post), the ⏳ is gone again and
the old post stays.
