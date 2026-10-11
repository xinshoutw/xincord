# core-backup Specification

## Purpose
Backs up the working directory's `data/` while the bot runs: a consistent copy of each database
into `backups/`, complete or not at all, the newest kept.

## Requirements

### Requirement: Online backup
`python -m xincord.core.backup` SHALL copy `data/` of the working directory into a new directory of
`backups/` named after the UTC time, while the bot runs: each SQLite database through SQLite's
backup API, every other file as it is, and no journal, WAL or shared-memory file. The directory
SHALL get its name only once the copy is complete; a failed backup SHALL leave nothing behind.

#### Scenario: A consistent copy while the bot writes
- **WHEN** a database in `data/` holds a committed row and another connection's uncommitted row,
  and a backup runs
- **THEN** the backup's copy holds the committed row only, the other files are copied as they are,
  and the backup holds no journal file

#### Scenario: A failed backup
- **WHEN** a copy fails during a backup
- **THEN** the error ends the backup and `backups/` holds no part of it

#### Scenario: Two backups in one second
- **WHEN** a backup runs in the same second as the previous one
- **THEN** it fails before copying anything, naming the backup of that second, which stays as it
  was

### Requirement: Backup retention
A backup SHALL keep the newest `--keep` backups, 7 by default, its own included, and delete the
older ones. Nothing else in `backups/` SHALL be touched.

#### Scenario: The oldest go
- **WHEN** `backups/` holds 8 backups and a file of the operator's, and a backup runs with the
  default
- **THEN** the 7 newest backups remain, the new one included, and the operator's file stays

### Requirement: Backup command
The command SHALL take an optional destination, `backups` by default, and `--keep`, print the new
backup's path with its file count and size, and exit with status 2 when the working directory has
no `data/` or `--keep` is below 1.

#### Scenario: Output and errors
- **WHEN** the command runs in a bot's directory, then without `data/`, then with `--keep 0`
- **THEN** it prints the backup's path, file count and size, then exits with status 2 twice
