## ADDED Requirements

### Requirement: Time zone from .env
The `bot` service SHALL take its `TZ` from `.env`, `UTC` when unset, so that the plugins that use
the host's local time (Giveaway's typed end times, Ticket's archive times, NtustAnnouncements'
`{{now}}`) follow the operator's zone. `.env.example` SHALL show `TZ` as a commented example.

#### Scenario: Compose and the example
- **WHEN** `compose.yaml` and `.env.example` are read
- **THEN** the `bot` service's environment sets `TZ` to `${TZ:-UTC}`, and `.env.example` holds a
  commented `TZ=` line
