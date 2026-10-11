## Why

Production keeps its data, `xincord.db` and ChatLogger's message files, in one Docker volume on one
host, and nothing backs it up: the only advice was to copy the files with the bot stopped. The
owner asked on 2026-10-12 for an online backup that a schedule can run.

## What Changes

- `python -m xincord.core.backup [DESTINATION] [--keep N]` copies `data/` into
  `backups/<UTC time>/` while the bot runs: SQLite databases through SQLite's backup API, a
  consistent copy, and other files as they are. A backup appears under its name only once it is
  complete; the newest 7 (`--keep`) stay and older ones go.
- Under compose, `docker compose exec -T bot python -m xincord.core.backup` writes the backup into
  `backups/` beside `compose.yaml`, on the host; the README says to schedule it and to copy
  `backups/` off the host. The ignore files leave `backups/` out.

## Capabilities

### New Capabilities

- `core-backup`: the online backup command and its retention.

### Modified Capabilities

- `deployment`: the build context leaves out `backups/`.

## Impact

New `xincord.core.backup`, `tests/core/test_backup.py`, `.gitignore`, `.dockerignore`, README,
`docs/porting/owner-review.md`, `docs/porting/decisions.md` (Amendment 10),
`tests/test_container.py`. Production schedules it after the next release.
