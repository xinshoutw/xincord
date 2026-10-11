## ADDED Requirements

### Requirement: Dependabot opens security updates only
`.github/dependabot.yml` SHALL configure only the `uv` and `github-actions` ecosystems, both at the
repository root, each with a schedule and an open pull request limit of 0, so that Dependabot opens
no version updates while its security updates still come. Their commit messages SHALL start with
`build` for uv and `ci` for GitHub Actions, without a scope.

#### Scenario: Version updates are off
- **WHEN** `.github/dependabot.yml` is read
- **THEN** `uv` and `github-actions` are configured at `/`, each with a schedule and
  `open-pull-requests-limit: 0`, and no other ecosystem is configured

#### Scenario: Commit messages
- **WHEN** `.github/dependabot.yml` is read
- **THEN** uv's commit messages are prefixed `build` and GitHub Actions' `ci`, without a scope

### Requirement: Renovate opens version updates
`.github/renovate.json` SHALL extend Renovate's recommended config, create branches on Mondays in
Asia/Taipei, offer releases 7 days old with strict internal checks, leave security updates to
Dependabot and title commits `build:`, or `ci:` for GitHub Actions, without a scope. It SHALL
update `uv.lock`, the SHA-pinned actions, the Dockerfile's images, compose's Lavalink image and
`.python-version`, not `requires-python`, the workspace's packages or compose's local image.

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
the Lavalink plugins of `lavalink/application.yml` from Maven at
`https://maven.lavalink.dev/releases`, the repository that the node downloads them from.

#### Scenario: OpenSpec CLI
- **WHEN** the repository's files, except archived changes and research notes, are searched for a
  pinned OpenSpec CLI
- **THEN** each pin is in a file that the npm regex manager reads, its pattern matches every pin,
  and all pins name the same version

#### Scenario: Lavalink plugins
- **WHEN** the Maven regex manager's pattern is applied to `lavalink/application.yml`
- **THEN** it finds youtube-source and LavaSrc with their exact versions, looked up at
  `https://maven.lavalink.dev/releases`

### Requirement: Renovate automerges patch updates and lock-file maintenance only
Renovate SHALL automerge patch updates, in PRs of their own, and the monthly lock-file maintenance,
merging squashed PRs itself once their checks pass, never through the platform's automerge. Minor
and major updates SHALL wait for the owner; Python's never automerge. Updates whose source gives no
release dates (GHCR images, GitHub's runners) SHALL skip the release age and wait for the owner.

#### Scenario: Patch updates automerge
- **WHEN** a patch update of a locked package, an action, the Python image, the OpenSpec CLI or a
  Lavalink plugin is resolved
- **THEN** it automerges

#### Scenario: Minor and major updates wait
- **WHEN** a minor or major update is resolved
- **THEN** it does not automerge, and the rule that keeps Python's minor and major updates waiting
  comes after every rule that automerges

#### Scenario: Lock-file maintenance
- **WHEN** the lock-file maintenance settings are read
- **THEN** it runs on the first day of each month and automerges

#### Scenario: Renovate waits for CI
- **WHEN** the automerge settings are read
- **THEN** Renovate merges PRs itself with squash, the platform's automerge is off, tests are not
  ignored, and CI runs on pull requests

#### Scenario: Updates without release dates
- **WHEN** an update of a GHCR image or of GitHub's runner is resolved
- **THEN** it has no release age, and it does not automerge
