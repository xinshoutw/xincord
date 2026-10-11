## Why

The container's time zone is UTC, so three plugins that read the host's local time are 8 hours off
on the owner's host: Giveaway reads typed end times in it (unless its `timeZone` is set), Ticket
names its archive threads and markers in it, and NtustAnnouncements fills `{{now}}` with it. The
review queue told the operator to set `timeZone` or `TZ` before cutover; on 2026-10-11 the owner
asked for one setting instead.

## What Changes

- `compose.yaml` passes `TZ` from `.env` to the `bot` service, `UTC` when unset (the image's zone
  data, `/usr/share/zoneinfo`, resolves IANA names).
- `.env.example` documents `TZ` with `Asia/Taipei` as a commented example.
- Giveaway's `timeZone` keeps its meaning (empty: the host's zone, now `TZ`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `deployment`: the bot's time zone comes from `TZ` in `.env` (one requirement added).

## Impact

`compose.yaml`, `.env.example`, `README.md` (Docker) and the container tests. No code change.
Operators who want local times set `TZ` in `.env`; without it nothing changes.
