## Why

PyPI refused the owner's second pending trusted publisher on 2026-10-12: a pending publisher is
unique by repository, workflow and environment, so the two new projects `xincord` and
`xincord-plugins` cannot both wait for their first upload under the release workflow's one `pypi`
environment. The owner chose one environment per package.

## What Changes

- The release workflow's PyPI job publishes `xincord` only; a new job publishes `xincord-plugins`
  after it, in the new environment `pypi-plugins`. Both run only for tags from 1.0.0 on, download
  only their own files from the GitHub Release and publish them with trusted publishing.
- The `pypi-plugins` environment exists (created on the owner's approval, like `pypi`): the owner
  as required reviewer, deployments from `v*` tags only. A release from 1.0.0 on asks for two
  approvals.
- README, "Releasing", says so.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `release`: "PyPI from 1.0.0" names a job and an environment per package.

## Impact

`.github/workflows/release.yml`, `tests/test_release.py`, `README.md`. The owner registers the
pending publishers `xincord` (environment `pypi`) and `xincord-plugins` (environment
`pypi-plugins`) on PyPI.
