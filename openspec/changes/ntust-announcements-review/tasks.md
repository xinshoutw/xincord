## 1. Refused texts and the review

- [ ] 1.1 xfail tests for "Answers that hold a refused text are retried", "The review prompt" and
      "The prompt is filled in one pass" (`{{markdown}}`)
- [ ] 1.2 `reject-texts`, `review-prompt`, `fill_prompt`'s token, `Converter.review`; remove the
      markers

## 2. Posted messages and the redo

- [ ] 2.1 xfail tests for "Posted messages are remembered" and "A reviewer's cross mark redoes a
      post"
- [ ] 2.2 `store.Announcements`, `Watcher._post` recording the IDs, `Watcher.redo`, the cog's
      listener and `reviewers`; remove the markers

## 3. Splitting at the structure

- [ ] 3.1 xfail tests for "Long content is split at its structure" (headings, bold lines, blank
      lines, list items, short parts, consecutive breaks); v3's comparison keeps the contents
      without them
- [ ] 3.2 The new `split`; remove the markers

## 4. Prompts and close

- [ ] 4.1 The new bundled `prompt` and `review-prompt` with their comments; porting guide rows
- [ ] 4.2 Gate passes, push, CI green
- [ ] 4.3 The manual check on the owner's test guild (design)
- [ ] 4.4 Archive the change and run `openspec validate --all --strict`; update `HANDOFF.md` and
      `docs/porting/owner-review.md` (the new copy)
