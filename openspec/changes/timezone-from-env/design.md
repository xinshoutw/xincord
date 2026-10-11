## Context

The bot runs in `python:3.14.N-slim-trixie`, whose zone is UTC; Debian's zone data is in the
image (`/usr/share/zoneinfo/Asia/Taipei` exists, and `TZ=Asia/Taipei` gives `+08:00` in Python).
Giveaway reads typed end times in `timeZone` or else the host's zone; Ticket formats its archive
thread names and markers with `astimezone(None)`; NtustAnnouncements' `{{now}}` is the host's
local time, as v3's. v3 ran on a host in Taiwan.

## Goals / Non-Goals

**Goals:** one setting for the bot's local time, kept out of the tracked files, UTC when unset.

**Non-Goals:** time zone keys in each plugin's config (Giveaway's `timeZone` stays); the Lavalink
node's zone (its logs only).

## Decisions

### `TZ` from `.env`

`environment: {TZ: "${TZ:-UTC}"}` on the `bot` service. `.env` already holds the operator's
settings for compose (the Lavalink password), so the zone stays out of git. Alternatives: a fixed
`TZ: Asia/Taipei` in `compose.yaml` (wrong for operators elsewhere once the repository is
public), or a core config key (the process's zone is the container's concern).

### The example stays commented

`.env.example` shows `# TZ=Asia/Taipei`: copying the file changes nothing until the operator
chooses a zone.

## Manual check

With `TZ=Asia/Taipei` in `.env`: `docker compose up -d` recreates the bot, and
`docker compose exec bot date` and Python's local time show `+08:00`.
