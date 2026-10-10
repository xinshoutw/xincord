## 1. Core: a data directory per plugin

- [x] 1.1 xfail tests for "Plugins get a data directory" against a stub (`Bot(..., data=...)`
      accepted and kept, `PluginContext.data_directory` raising); every `Bot(...)` call names its
      data directory
- [x] 1.2 Give each context `data/<Name>/` and let the program pass `data/`; remove the markers

## 2. Config

- [x] 2.1 xfail tests for "The config keeps v3's key and bounds the stored messages" (the 5-year
      default, `max_file_size_mb`) and the default of "Old messages"
- [x] 2.2 Add `max_file_size_mb`, set `retention_days` to 1826 in `Config` and the bundled
      `config.yaml`; remove the markers

## 3. File names and ranges

- [x] 3.1 xfail tests for "Stored messages live in the plugin's own files" and "A new message file
      starts when the newest is full": names, routing and the next start against stubs in
      `files.py`
- [x] 3.2 Implement `files.py`; remove the markers

## 4. Message files

- [x] 4.1 xfail tests for "Stored messages live in the plugin's own files", "A new message file
      starts when the newest is full" and "The message files are open while the plugin is loaded"
      against a stub `MessageFiles` (first file, routing, splits, late messages, reopening, a
      failing split, closing)
- [ ] 4.2 Implement `MessageFiles` (row-level retention only); remove the markers

## 5. The plugin on its files

- [ ] 5.1 xfail tests for the plugin's side of the three requirements of 4.1 (no file before the
      first message, messages of older files edited and deleted, the old table dropped, the size
      from the config, unload, reload, failed load)
- [ ] 5.2 Open the files in `cog_load`, close them in `cog_unload`, drop the old table in `setup`,
      remove the store-based `MessageLog`; remove the markers

## 6. Expired files

- [ ] 6.1 xfail tests for "Stored messages are kept for the retention period": `files.expired` and
      whole files expiring in `MessageFiles.prune` and through the plugin at READY
- [ ] 6.2 Delete the expired files; remove the markers

## 7. Checks and docs

- [ ] 7.1 The wheel ships the plugin's files; image check (`docker compose build`, `docker compose
      run --rm -T bot --no-online` with ChatLogger, a probe that stores messages into the volume)
- [ ] 7.2 Porting guide rows and conventions, port-plugin skill notes; audit the scenarios against
      the tests and `design.md`
- [ ] 7.3 Push the work so far (CI green); cross-review (a subagent); record its findings in the
      deltas and `design.md`

## 8. Close

- [ ] 8.1 Gate passes, push, CI green
- [ ] 8.2 Archive the change and run `openspec validate --all --strict`
- [ ] 8.3 Update `HANDOFF.md` and `docs/porting/owner-review.md`; push; CI green
