# project-tooling Specification

## Purpose
Defines how the xincord repository is packaged and which automated checks guard every commit.

## Requirements

### Requirement: Two distributions share the xincord namespace
The repository SHALL build a `xincord` distribution providing the import package `xincord.core`
and a `xincord-plugins` distribution providing `xincord.plugins`. Neither distribution SHALL ship
`xincord/__init__.py`, so `xincord` stays a namespace that both can extend.

#### Scenario: Both import packages load
- **WHEN** the workspace is synced and `xincord.core` and `xincord.plugins` are imported
- **THEN** both imports succeed

#### Scenario: xincord is a namespace package
- **WHEN** the `xincord` package is inspected after import
- **THEN** it has no `__file__` and its search path covers both distributions

### Requirement: Python sources contain no CJK characters
The pre-commit configuration SHALL reject a Python file that contains a CJK character: CJK
symbols and punctuation, kana, CJK ideographs (including extensions and compatibility
ideographs) or fullwidth forms. Other non-ASCII characters SHALL be allowed.

#### Scenario: CJK ideograph is rejected
- **WHEN** a Python file contains a CJK unified ideograph
- **THEN** the check reports that file

#### Scenario: Fullwidth punctuation is rejected
- **WHEN** a Python file contains a fullwidth comma or an ideographic full stop
- **THEN** the check reports that file

#### Scenario: Other text passes
- **WHEN** a Python file contains only ASCII, accented Latin letters, or emoji
- **THEN** the check passes

### Requirement: Commit messages are ASCII Conventional Commits
The commit-msg hook SHALL accept a message only when its first line is `type(scope): subject` or
`type: subject`, the type is one of feat, fix, test, refactor, docs, build, ci or chore, the scope
is core, build, ci, docs or `plugin-<name>` in lowercase kebab case, and the whole message is
ASCII. Comment lines and everything after the scissors line of `git commit -v` SHALL be ignored.

#### Scenario: Valid message is accepted
- **WHEN** the message is `feat(plugin-auto-role): assign roles on join` with an ASCII bullet body
- **THEN** the hook accepts it

#### Scenario: Non-ASCII text is rejected
- **WHEN** the subject or the body contains a CJK character
- **THEN** the hook rejects the message and names the offending line

#### Scenario: Unknown type or scope is rejected
- **WHEN** the type is `feature` or the scope is `Core`
- **THEN** the hook rejects the message

#### Scenario: Comments and the verbose diff are ignored
- **WHEN** non-ASCII text appears only in `#` comment lines or below the scissors line
- **THEN** the hook accepts the message

### Requirement: Commit messages carry no tool attribution
The commit-msg hook SHALL reject a message with a tool attribution line: a `Co-Authored-By:` or
`Claude-Session:` trailer, or `Generated with [Claude Code]`, in any letter case. Comment lines and
the verbose diff SHALL be ignored as above.

#### Scenario: Attribution lines are rejected
- **WHEN** the body contains a `Co-Authored-By:` or `Claude-Session:` line, or `Generated with [Claude Code]`
- **THEN** the hook rejects the message and names the offending line

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
`https://maven.lavalink.dev/releases`, the repository that the node downloads them from, and leave
a plugin pinned to a snapshot's commit alone.

#### Scenario: OpenSpec CLI
- **WHEN** the repository's files, except archived changes and research notes, are searched for a
  pinned OpenSpec CLI
- **THEN** each pin is in a file that the npm regex manager reads, its pattern matches every pin,
  and all pins name the same version

#### Scenario: Lavalink plugins
- **WHEN** the Maven regex manager's pattern is applied to `lavalink/application.yml`
- **THEN** it finds youtube-source and LavaSrc with their exact releases or snapshot commits,
  looked up at `https://maven.lavalink.dev/releases`, and a rule disables updates of a version that
  is a 40-character commit

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
