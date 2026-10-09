## 1. Workspace

- [x] 1.1 Root `pyproject.toml` (xincord core, workspace, tool configuration) and `.python-version`
- [x] 1.2 `packages/xincord-plugins` member and both import packages
- [x] 1.3 Smoke tests for "Two distributions share the xincord namespace"
- [x] 1.4 `scripts/gate.sh` passes

## 2. Commit-message check (xfail-first)

- [x] 2.1 Tests for "Commit messages are ASCII Conventional Commits", committed as xfail
- [x] 2.2 Implement `scripts/check_commit_msg.py`, remove the xfail markers

## 3. Hooks and CI

- [x] 3.1 `.pre-commit-config.yaml` with the CJK pygrep hook; tests for "Python sources contain
      no CJK characters"; `prek install`
- [x] 3.2 Claude Code hooks in `.claude/settings.json`
- [x] 3.3 `.github/workflows/ci.yml`

## 4. Documentation

- [x] 4.1 `AGENTS.md`, `README.md`, `.gitignore`
- [x] 4.2 `docs/porting-guide.md`
- [x] 4.3 `.claude/skills/port-plugin/SKILL.md`
- [x] 4.4 Amend resolution 2 in `docs/porting/decisions.md`

## 5. Close

- [ ] 5.1 Gate passes, push, CI green
- [ ] 5.2 Archive the change and run `openspec validate --all --strict`
