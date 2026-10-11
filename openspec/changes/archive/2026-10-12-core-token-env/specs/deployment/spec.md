## ADDED Requirements

### Requirement: Token from .env
The `bot` service SHALL take `XINCORD_TOKEN` from `.env`, empty when unset, so that the bot token can
stay out of `config.yaml` and off the command line. `.env.example` SHALL show `XINCORD_TOKEN` as a
commented line.

#### Scenario: Compose and the example
- **WHEN** `compose.yaml` and `.env.example` are read
- **THEN** the `bot` service's environment sets `XINCORD_TOKEN` to `${XINCORD_TOKEN:-}`, and
  `.env.example` holds a commented `XINCORD_TOKEN=` line
