## 1. Tests first

- [x] 1.1 xfail tests for `release_version` and the script's exit codes, against a stub
- [x] 1.2 xfail tests for the workflow: trigger, signature, image, release, dry run, PyPI job,
  pinned actions and permissions

## 2. Implementation

- [x] 2.1 `scripts/release_version.py`
- [x] 2.2 `.github/workflows/release.yml`

## 3. Docs and close

- [ ] 3.1 README (releasing), AGENTS.md, HANDOFF, the review queue (the owner's settings)
- [ ] 3.2 Archive, `validate --all --strict`, push, CI green
