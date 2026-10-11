## MODIFIED Requirements

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
