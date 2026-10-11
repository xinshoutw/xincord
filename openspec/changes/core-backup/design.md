## Decisions

### SQLite's backup API

The bot keeps its connections open, and a plain file copy taken during a write can be torn.
`sqlite3.Connection.backup` copies the database's pages under a read lock in one step, retrying
while a writer holds the lock, so the copy is the last committed state; the bot's writes wait at
most for that step (its busy timeout is 5 s, the copy of a 30 MB file takes well under one). A
database is recognised by its 16-byte header, not its name, so a plugin's own SQLite files are
copied the same way. Journal, WAL and shared-memory files are left out: the copy needs none.

### Complete or nothing

The files go into `backups/.<time>.partial/`, renamed to `backups/<time>/` at the end; on an error
the partial directory is removed and the error ends the command. A schedule never sees half a
backup as one, and retention counts complete backups only.

### Retention

Backups are the directories named `YYYYMMDDTHHMMSSZ`, the UTC time they were taken, which sort by
age. The newest `--keep` stay; anything else in the destination is the operator's and stays.

### Where it runs

In the bot's container, where `data/` is the volume and `backups/` the bind-mounted directory of
`compose.yaml`: the backup lands on the host without a second mount, owned as the bot's other
files. A schedule on the host runs `docker compose exec -T bot python -m xincord.core.backup`
(cron, or launchd on macOS) and copies `backups/` elsewhere: a backup on the same disk guards
against mistakes, not against the disk.
