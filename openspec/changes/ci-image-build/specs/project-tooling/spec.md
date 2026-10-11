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
- **THEN** it is `build`, or `ci` for GitHub Actions and their runners, also where the presets of
  `config:recommended` give another type, and no scope is set

#### Scenario: Managers
- **WHEN** the enabled managers are read
- **THEN** they are pep621 with `uv.lock` (lock-file updates within the ranges), github-actions
  (SHA pins with version comments), dockerfile, docker-compose, pyenv and the custom regex managers,
  and uv's image and build backend share one group

#### Scenario: Ignored dependencies
- **WHEN** `requires-python`, the workspace's own packages or compose's `xincord` image is resolved
- **THEN** Renovate leaves it alone
