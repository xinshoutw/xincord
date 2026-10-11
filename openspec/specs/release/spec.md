# release Specification

## Purpose
Releases xincord from a GPG-signed `v*` tag: both distributions, a multi-arch GHCR image and the GitHub Release, with PyPI from 1.0.0.

## Requirements

### Requirement: Signed release tags
Pushing a `v*` tag SHALL run the release workflow, which SHALL fail unless the tag is an annotated
tag with a valid signature by a GPG key of the repository owner's GitHub account and names the
version that both distributions declare. `scripts/release_version.py` SHALL print that version and
fail when the distributions disagree or a given tag names another version.

#### Scenario: Trigger and signature
- **WHEN** `.github/workflows/release.yml` is read
- **THEN** it runs on pushed `v*` tags and on a manual dispatch, and on a tag it imports the owner's
  GitHub GPG keys and verifies the tag before anything is built

#### Scenario: Matching versions
- **WHEN** both distributions declare 1.2.3 and the tag is `v1.2.3`, or no tag is given
- **THEN** `release_version` returns `1.2.3`

#### Scenario: Mismatched versions
- **WHEN** the distributions declare different versions, or the tag names another version
- **THEN** `release_version` fails with a message naming the versions, and the script exits 1

### Requirement: Release artifacts
On a tag, the workflow SHALL build both distributions with `uv build --all-packages`, build the image
for `linux/amd64` and `linux/arm64`, push it to `ghcr.io/<owner>/xincord` tagged with the version
and `latest` and labelled with the repository as its source, and create the GitHub Release for the
verified tag with the distributions attached, notes listing the commits since the previous tag,
marked as a prerelease while the version is 0.x.

#### Scenario: Image
- **WHEN** the workflow's image step is read
- **THEN** it builds both platforms, pushes only on a tag, tags the version and `latest`, and labels
  the repository as the source

#### Scenario: GitHub Release
- **WHEN** the workflow's release step is read
- **THEN** it runs only on a tag, verifies the tag, attaches `dist/*`, uses notes made from the
  commits since the previous tag, and marks 0.x versions as prereleases

### Requirement: Dry runs
A manual dispatch SHALL run the version check and both builds without pushing the image, creating a
release or publishing.

#### Scenario: Manual dispatch
- **WHEN** the workflow runs without a tag
- **THEN** the steps that log in, push, release or publish are skipped

### Requirement: PyPI from 1.0.0
The workflow SHALL publish to PyPI only for tags of version 1.0.0 or later, one job per
distribution with OpenID Connect trusted publishing and no stored token: `xincord` in the `pypi`
environment, then `xincord-plugins` in `pypi-plugins`, each uploading its own files from the GitHub
Release. Every action in the workflow SHALL be pinned to a commit SHA with its version in a
comment, and jobs SHALL get only the permissions they use.

#### Scenario: Publishing waits for 1.0.0
- **WHEN** the PyPI jobs are read
- **THEN** both run only on tags outside `v0.`, `xincord`'s in the `pypi` environment and
  `xincord-plugins`' in `pypi-plugins` after it, each with `id-token: write`, downloading its own
  files from the Release and publishing them with trusted publishing

#### Scenario: Pinned actions and permissions
- **WHEN** every `uses:` and permission of the workflow is read
- **THEN** each action names a 40-character commit SHA and a version comment, the workflow's
  default permission is `contents: read`, and only the release job may write contents and packages
