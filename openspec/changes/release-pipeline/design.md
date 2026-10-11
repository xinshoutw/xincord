## Context

Amendment 4 of `docs/porting/decisions.md`: releases start from a GPG-signed `v*` tag that the owner
pushes (Claude only with the owner's approval); images go to GHCR, multi-arch, private until the
repository is public; PyPI only from 1.0.0. Both distributions share one version (B16).

## Decisions

- **One job builds and releases; another publishes.** The release job verifies, builds, pushes the
  image and creates the Release. The PyPI job downloads the Release's files, so PyPI gets exactly
  what the Release shows, and runs in the `pypi` environment, whose required reviewer the owner sets.
- **Signature check in CI.** The job imports `https://github.com/<owner>.gpg` and runs
  `git verify-tag`, so an unsigned or foreign tag releases nothing.
- **Version check as a script.** `scripts/release_version.py` reads both `pyproject.toml` files with
  `tomllib`; the runner's Python 3.12 has it. The script is tested like `check_commit_msg.py`.
- **Notes from commits.** `git log` of the commit subjects since the previous tag: the history is
  Conventional Commits, and no changelog file or extra action is needed.
- **Prereleases.** 0.x versions are prereleases (B16: 0.x until the cutover).
- **QEMU for arm64.** One runner builds both platforms through QEMU; native arm64 runners are not
  assumed for a private repository.
- **`uv publish --trusted-publishing always`** instead of a publishing action.
- **Dry runs.** A manual dispatch runs every check and build and skips login, push, release and
  publishing (`github.ref_type == 'tag'` guards them).

## Owner's settings before the first release

- A `pypi` environment with the owner as required reviewer (repository settings).
- Pending trusted publishers on PyPI for `xincord` and `xincord-plugins` (workflow `release.yml`,
  environment `pypi`), before the first 1.x tag.
- The GHCR package stays private with the repository; make it public with the repository.

## Risks

- QEMU makes the arm64 build slow (several minutes).
- A key that GitHub does not list (or an expired one) fails the signature check; the owner's signing
  key must stay on the GitHub account.
