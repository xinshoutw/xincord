## MODIFIED Requirements

### Requirement: Container image
The repository SHALL build an image from an exact `python:3.14.N-slim-trixie` tag that installs
both distributions with an exact uv image version from `uv.lock`, without development dependencies
and not editable, and that runs `xincord` with the container's arguments as a non-root user in
`/bot`. The build context SHALL exclude the local virtual environment, git data, caches, the bot's
runtime files and the secrets file `.env`.

#### Scenario: Image definition
- **WHEN** the Dockerfile is read
- **THEN** it builds from an exact Python 3.14 slim trixie tag and an exact uv image version, runs
  `uv sync --locked --no-dev --all-packages --no-editable`, switches to a non-root user, works in
  `/bot` and has the entry point `xincord`

#### Scenario: Build context
- **WHEN** the `.dockerignore` file is read
- **THEN** it excludes `.venv`, `.git`, the tool caches, `config.yaml`, `plugins`, `data`,
  `backups` and `.env`
