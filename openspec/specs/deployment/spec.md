# deployment Specification

## Purpose
Packages xincord as a container image and runs it with docker compose on the owner's host.

## Requirements

### Requirement: Container image
The repository SHALL build an image from `python:3.14.8-slim-trixie` that installs both
distributions with uv 0.12.24 from `uv.lock`, without development dependencies and not editable,
and that runs `xincord` with the container's arguments as a non-root user in `/bot`. The build
context SHALL exclude the local virtual environment, git data, caches and the bot's runtime files.

#### Scenario: Image definition
- **WHEN** the Dockerfile is read
- **THEN** it builds from the pinned base and uv images, runs
  `uv sync --locked --no-dev --all-packages --no-editable`, switches to a non-root user, works in
  `/bot` and has the entry point `xincord`

#### Scenario: Build context
- **WHEN** the `.dockerignore` file is read
- **THEN** it excludes `.venv`, `.git`, the tool caches and `bot/`

### Requirement: Compose service
`compose.yaml` SHALL define a `bot` service built from the repository that bind-mounts the host
directory `./bot` at `/bot` for the config and plugin files, mounts the named volume `data` at
`/bot/data` for the database, keeps stdin open with a TTY for the console, runs an init process,
restarts unless stopped, allows 30 seconds to stop and rotates its logs.

#### Scenario: Service definition
- **WHEN** `compose.yaml` is read
- **THEN** the `bot` service has those settings and the `data` volume is declared
