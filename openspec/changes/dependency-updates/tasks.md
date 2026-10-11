## 1. Tests first

- [x] 1.1 xfail tests for Dependabot's security-only config (`tests/test_dependency_updates.py`)
- [x] 1.2 xfail tests for Renovate's schedule, commits, managers, ignored dependencies, regex
  managers and automerge policy
- [x] 1.3 Container checks accept any exact version of each pinned series

## 2. Configuration

- [ ] 2.1 `.github/dependabot.yml`
- [ ] 2.2 `.github/renovate.json`, checked once with `renovate-config-validator --strict`

## 3. Docs and close

- [ ] 3.1 AGENTS.md (the bots' PRs and the automerge policy), README, the review queue
- [ ] 3.2 Archive, `validate --all --strict`, push, CI green
