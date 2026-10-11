## ADDED Requirements

### Requirement: Image checked in CI
The `ci` workflow SHALL build the image for linux/amd64 on every push to `main` and every pull
request without pushing it, and run in it the import of every installed plugin and `xincord
--no-online`. The actions it uses SHALL be pinned to commits.

#### Scenario: Image job
- **WHEN** `.github/workflows/ci.yml` is read
- **THEN** a job builds the Dockerfile for linux/amd64 without pushing, loads the image and runs in
  it the plugins' import and `xincord --no-online`, and every action it uses is pinned to a commit
