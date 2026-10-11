## Why

On 2026-10-11 the owner decided how dependencies stay current (`docs/porting/decisions.md`,
Amendment 5): Dependabot opens security updates only; Renovate opens version updates and
automerges patch updates and lock-file maintenance after CI passes; minor and major updates wait
for the owner. The owner installed the Renovate app, whose onboarding PR #1 was closed: Renovate
waits for its config on `main`. The owner also enabled the dependency graph, Dependabot alerts and
Dependabot security updates. v3 had no dependency bots, so there is no Kotlin source to port.

## What Changes

- `.github/dependabot.yml`: the `uv` and `github-actions` ecosystems at `/`, weekly, with
  `open-pull-requests-limit: 0`, which turns version updates off while security updates still
  come (they ignore that limit); commit messages prefixed `build` and `ci`. Docker, Docker Compose
  and pre-commit are left out: Dependabot has no security updates for them.
- `.github/renovate.json`, plain JSON that the tests read: `config:recommended`, Mondays in
  Asia/Taipei, a release offered once it is 7 days old (`minimumReleaseAge`, strict internal
  checks), Renovate's own vulnerability alerts off, commits and PR titles `build: ...` (`ci: ...`
  for GitHub Actions) without a scope. Managers: pep621 with `uv.lock` (lock-file updates within
  the ranges; `requires-python` and the workspace's own packages left alone), github-actions (SHA
  pins with version comments), dockerfile, docker-compose (the Lavalink image; compose's locally
  built bot image is ignored), pyenv, and two regex managers: the OpenSpec CLI's version wherever
  the gate, a workflow or a doc pins it (npm), and Lavalink's two plugins in
  `lavalink/application.yml` (Maven, from `https://maven.lavalink.dev/releases`, the repository
  the node downloads them from).
- Automerge: patch updates and the monthly lock-file maintenance only, as squashed PRs that
  Renovate merges itself once CI passes (`platformAutomerge: false`: the repository has no required
  status checks, so GitHub's auto-merge would not wait for CI). Patch updates get PRs of their own,
  so a waiting minor update does not hold them back. Minor and major updates wait for the owner,
  and a Python minor or major update never automerges. The GHCR images (uv, Lavalink) carry no
  release dates that Renovate can read, so the 7 days would hold them forever: they come without
  the wait and wait for the owner instead.
- The container checks accept any exact version of each pinned series (Python 3.14's slim trixie
  image, an exact uv, Lavalink 4.2 or a later 4.x), so that Renovate's patch PRs pass CI; the
  `deployment` requirements say so.
- `tests/test_dependency_updates.py` parses both files and checks this division of labor; AGENTS.md
  describes the bots' PRs and the automerge policy; README names the bots.

Out of scope: releases, PyPI publishing and GHCR images (Amendment 4, a later change); pinning the
uv that CI installs; Dependabot version updates; required status checks and other repository
settings; running Renovate's config validator in the gate (a heavy download).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-tooling`: Dependabot opens security updates only, Renovate opens version updates,
  including the versions that no built-in manager reads, and Renovate automerges patch updates and
  lock-file maintenance only (four requirements added).
- `deployment`: the image and the Lavalink service pin an exact version of a series rather than one
  given version (two requirements modified).

## Impact

New files `.github/dependabot.yml`, `.github/renovate.json` and `tests/test_dependency_updates.py`;
`tests/test_container.py` checks the pins by series; AGENTS.md, README.md and
`docs/porting/owner-review.md`. No product code and no dependency change. Once `main` has the
config, Renovate starts on its schedule and opens a Dependency Dashboard issue listing what waits.
