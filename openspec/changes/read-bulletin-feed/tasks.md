# Tasks

## 1. Failing tests

- [ ] 1.1 Add stubs for the feed client (`bulletin.py`), the loop's logic (`feed.py`), the state
  document (`store.py`) and the rewrite's messages, raising `NotImplementedError`
- [ ] 1.2 Write the tests for "The config names the feed and the boards", "The feed is read from
  READY until the plugin unloads", "The first read starts at the feed's end", "Notify-worthy
  announcements on a configured board wait for their rewrite", "Waiting announcements are posted
  to their boards' channels", "The feed's position and the waiting announcements are stored",
  "Problems are logged without flooding" and "A rewritten announcement becomes its title link,
  its rewrite and its attachments"; run them and see each fail for the expected reason
- [ ] 1.3 Commit them marked `xfail(strict=True)`, the gate green

## 2. Implementation

- [ ] 2.1 Implement the feed client with pydantic models of the API answers
- [ ] 2.2 Implement the state document and the rewrite's messages
- [ ] 2.3 Implement the loop: first read, waiting, posting, retries, logging
- [ ] 2.4 Replace the config, the bundled `config.yaml` and the cog; remove the scraper, the
  model clients, the redo and their tests and fixtures
- [ ] 2.5 Remove the xfail markers; run the gate; commit

## 3. Docs and archive

- [ ] 3.1 Update `docs/architecture.md`, `docs/plugin-conventions.md`, `docs/pitfalls.md`,
  `docs/owner-review.md` and `README.md`
- [ ] 3.2 Run `scripts/gate.sh`, archive the change, then validate all specs strictly
