## Context

The owner decided on 2026-10-11 (decisions.md, Amendment 5) that Dependabot opens security updates
and Renovate opens version updates. Dependabot's security updates cover uv and GitHub Actions but
not Docker, Docker Compose or pre-commit; Renovate reads every pin in the repository, including the
ones in plain files. The repository has no required status checks.

## Decisions

- **Dependabot, security only.** `open-pull-requests-limit: 0` turns its version updates off;
  security updates ignore that limit (docs.github.com, Dependabot options reference). A schedule is
  still required by the file format.
- **Renovate, everything else.** `config:recommended`, Mondays in Asia/Taipei, a 7-day release age
  with strict internal checks so that no branch appears before the wait ends, and its own
  vulnerability alerts off so that a security fix never arrives twice.
- **Automerge.** Patch updates (in PRs of their own, `separateMinorPatch`) and the monthly lock-file
  maintenance. Renovate merges squashed PRs itself after the checks pass (`platformAutomerge`
  false): GitHub's auto-merge would merge at once without required checks. Minor and major updates
  wait for the owner; Python's never automerge.
- **No release dates.** GHCR images (uv, Lavalink) and GitHub's runners give Renovate no release
  timestamps, so a release age would hold them forever: they skip it and do not automerge.
- **Pins in plain files.** A regex manager reads the OpenSpec CLI version from npm in the gate,
  AGENTS.md and HANDOFF.md; another reads the Lavalink plugins from
  `https://maven.lavalink.dev/releases`, where the node downloads them.
- **Ignored.** `requires-python`, the workspace's own packages (`xincord` may exist on PyPI under
  someone else) and compose's local `xincord` image.
- **Container checks by series.** `tests/test_container.py` asserted exact versions, which would
  fail every Renovate patch PR; it now accepts any exact version of the pinned series.
- **Commit messages.** `build:` and `ci:` without a scope, which AGENTS.md's scope list does not
  need to cover.

## Risks

- GitHub documents Dependabot's uv support at uv 0.11, and the project locks with uv 0.12. If
  Dependabot's uv security PRs fail on the lock file, turn Renovate's `vulnerabilityAlerts` on.
- Renovate merges only when it runs; patch PRs may wait up to a week for the next Monday.
