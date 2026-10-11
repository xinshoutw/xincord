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

## 3. Prompts and close

- [ ] 3.1 The new bundled `prompt` and `review-prompt` with their comments; porting guide rows
- [ ] 3.2 Gate passes, push, CI green
- [ ] 3.3 The manual check on the owner's test guild (design)
- [ ] 3.4 Archive the change and run `openspec validate --all --strict`; update `HANDOFF.md` and
      `docs/porting/owner-review.md` (the new copy)
