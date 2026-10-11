## MODIFIED Requirements

### Requirement: Renovate opens version updates
`.github/renovate.json` SHALL extend Renovate's recommended config, create branches on Mondays in
Asia/Taipei, offer releases 7 days old with strict internal checks, leave security updates to
Dependabot and title commits `build:`, or `ci:` for GitHub Actions, without a scope. It SHALL
update `uv.lock`, the SHA-pinned actions, the Dockerfile's images, compose's Lavalink image and
`.python-version`, not `requires-python`, the workspace's packages or compose's xincord image.

#### Scenario: Weekly updates after a cooldown
- **WHEN** `.github/renovate.json` is read
- **THEN** it extends `config:recommended`, schedules Mondays in Asia/Taipei, waits 7 days with
  strict internal checks and turns Renovate's vulnerability alerts off

#### Scenario: Commit messages
- **WHEN** the commit type of an update is resolved
- **THEN** it is `build`, or `ci` for GitHub Actions and their runners, and no scope is set

#### Scenario: Managers
- **WHEN** the enabled managers are read
- **THEN** they are pep621 with `uv.lock` (lock-file updates within the ranges), github-actions
  (SHA pins with version comments), dockerfile, docker-compose, pyenv and the custom regex managers,
  and uv's image and build backend share one group

#### Scenario: Ignored dependencies
- **WHEN** `requires-python`, the workspace's own packages or compose's `xincord` image is resolved
- **THEN** Renovate leaves it alone

### Requirement: Renovate updates the versions that no manager reads
`.github/renovate.json` SHALL update the OpenSpec CLI's version from npm in every file of the gate,
the workflows and the docs that pins it, all of which SHALL pin the same version. It SHALL update
the Lavalink plugins of the node's config in `compose.yaml` from Maven at
`https://maven.lavalink.dev/releases`, the repository that the node downloads them from, and leave
a plugin pinned to a snapshot's commit alone.

#### Scenario: OpenSpec CLI
- **WHEN** the repository's files, except archived changes and research notes, are searched for a
  pinned OpenSpec CLI
- **THEN** each pin is in a file that the npm regex manager reads, its pattern matches every pin,
  and all pins name the same version

#### Scenario: Lavalink plugins
- **WHEN** the Maven regex manager's pattern is applied to `compose.yaml`
- **THEN** it finds youtube-source and LavaSrc with their exact releases or snapshot commits,
  looked up at `https://maven.lavalink.dev/releases`, and a rule disables updates of a version that
  is a 40-character commit
