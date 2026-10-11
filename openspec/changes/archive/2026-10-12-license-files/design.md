## Decisions

### A copy for the plugins

PEP 639's `license-files` take paths inside the project's directory, so the plugins' package
cannot name the root LICENSE. A copy is the plain way; a test fails when the two differ, so a change
of the root file reaches the copy. Alternative: a symlink, whose handling differs between build
backends and Windows checkouts.

## Manual check

`uv build --all-packages`: each wheel lists `License-File: LICENSE` in its metadata and holds
`*.dist-info/licenses/LICENSE`; each sdist holds `LICENSE`.
