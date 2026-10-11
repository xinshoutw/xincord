## Why

The owner decided on 2026-10-11 (decisions.md, Amendment 4) how xincord is released: a GPG-signed
`v*` tag that the owner pushes builds both distributions and a multi-arch image, pushes the image to
GHCR and creates the GitHub Release; PyPI publishing starts only at 1.0.0, after the cutover and once
the repository is public. Nothing releases xincord today.

## What Changes

- `.github/workflows/release.yml`, on a pushed `v*` tag:
  - checks that the tag carries a valid signature by a GPG key of the repository owner's GitHub
    account, and that it names the version of both distributions (`scripts/release_version.py`);
  - builds both distributions' wheels and sdists with `uv build --all-packages`;
  - builds the image for `linux/amd64` and `linux/arm64` and pushes it to
    `ghcr.io/<owner>/xincord:<version>` and `:latest`, labelled with the repository as its source;
  - creates the GitHub Release with the distributions attached and notes listing the commits since
    the previous tag, a prerelease while the version is 0.x;
  - publishes to PyPI with trusted publishing (OIDC, no token) only from 1.0.0, in the `pypi`
    environment that the owner protects, from the files attached to the Release.
- A manual run (`workflow_dispatch`) is a dry run: the checks and both builds, nothing pushed,
  released or published.
- `scripts/release_version.py` prints the version that a release tag must name, and fails when the
  two distributions disagree or the tag names another version.
- README and AGENTS.md describe how to cut a release; the review queue lists the owner's settings.

Out of scope: TestPyPI (public, like PyPI), build provenance attestations (private repositories need
GitHub Enterprise Cloud for them), a changelog file, version bumps by a bot.

## Capabilities

### New Capabilities

- `release`: tag-triggered releases of the distributions, the image and the GitHub Release.

### Modified Capabilities

None.

## Impact

New `.github/workflows/release.yml`, `scripts/release_version.py`, `tests/test_release.py`; README,
AGENTS.md, HANDOFF and the review queue. Nothing runs until the owner pushes a signed tag or starts
a dry run.
