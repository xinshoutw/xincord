## 1. Migration of v3 directories

- [x] 1.1 xfail tests for "v3 plugin switches migrate to the enabled list" (renamed plugins) and
      "Renamed plugins' v3 directories move to their new names"
- [x] 1.2 Add `RENAMED`, map the enabled list and move the directories in
      `xincord.core.migrate_v3`; remove the markers

## 2. Example

- [ ] 2.1 xfail tests for "The plugin installs as Example"
- [ ] 2.2 Rename the entry point and the plugin's texts; remove the markers

## 3. Calculator

- [ ] 3.1 xfail tests for "The plugin installs as Calculator"
- [ ] 3.2 Rename the package, the entry point, the cog, the log line, the tests and the fixtures;
      remove the markers

## 4. CustomCommands

- [ ] 4.1 xfail tests for "The plugin installs as CustomCommands"
- [ ] 4.2 Rename the package, the entry point, the cog, the log lines, the tests and the fixtures;
      remove the markers

## 5. WelcomeGoodbye

- [ ] 5.1 xfail tests for "The plugin installs as WelcomeGoodbye" and "Each guild's channels are
      stored" (the `WelcomeGoodbye` namespace)
- [ ] 5.2 Rename the package, the entry point, the cog, the namespace, the log lines, the tests
      and the fixtures; remove the markers

## 6. UptimeHeartbeat

- [ ] 6.1 xfail tests for "The plugin installs as UptimeHeartbeat" and "The status code decides
      what follows" (a log line with the new name)
- [ ] 6.2 Rename the package, the entry point, the cog, the log lines and task names, the tests;
      remove the markers

## 7. Feedback

- [ ] 7.1 xfail tests for "The plugin installs as Feedback", "The command is a localized guild
      command" (`/feedback`) and "v3's forms keep working" (`feedback:1:` IDs)
- [ ] 7.2 Rename the package, the entry point, the cog, the command and its `register.yaml` keys,
      the ID namespace, the log lines, the tests and the fixtures; remove the markers

## 8. Checks

- [ ] 8.1 Build the image and run `docker compose run --rm -T bot --no-online` with every ported
      plugin enabled in a temporary `bot/config.yaml`; clean up
- [ ] 8.2 Check that the old names remain only in the inventories, the archive, Kotlin citations,
      legacy prefixes, placeholder keys and the records of decisions and answers

## 9. Docs

- [ ] 9.1 Porting guide, port-plugin skill, `HANDOFF.md` sections 4 and 5 and the review queue's
      headings use the new names; the review queue gets a `rename-plugins` section and loses the
      image-check lines that 8.1 settles

## 10. Close

- [ ] 10.1 Gate passes, push, CI green
- [ ] 10.2 Archive the change and run `openspec validate --all --strict`
- [ ] 10.3 Update `HANDOFF.md`; push; CI green
