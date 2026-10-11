# HANDOFF: xincord

Updated 2026-10-12. Read this, then `AGENTS.md` and `docs/decisions.md`: the decisions are
accepted and binding; do not re-open them without asking the owner. Talk to the owner in
Traditional Chinese; everything written into the repository is English.

## State

xincord is a modular Discord bot on Python 3.14, uv and discord.py: the core and 18 plugins,
specified with OpenSpec and tested first (coverage 100%). Both of the owner's production bots run
it (below). What waits for the owner is in `docs/owner-review.md`; how it is built is in
`docs/architecture.md` and `docs/plugin-conventions.md`, hard-won facts in `docs/pitfalls.md`.

## Where things are

| What | Where |
|---|---|
| This project | `/Users/xinshou/IdeaProjects/xincord`, branch `main`, public at `github.com/xinshoutw/xincord` |
| Decisions, rules | `docs/decisions.md`, `AGENTS.md` (no CLAUDE.md on purpose) |
| Specs | `openspec/specs/`, active changes in `openspec/changes/` |
| Owner's open items | `docs/owner-review.md` |

## Rules (AGENTS.md has them all)

- Replies to the owner in Traditional Chinese; repository content in English; no CJK in `*.py`;
  commit messages ASCII, Conventional Commits (scopes `core`, `build`, `ci`, `docs`,
  `plugin-<name>`), GPG-signed, without attribution lines.
- Code changes go through OpenSpec and xfail-first tests: the failing test is committed with
  `@pytest.mark.xfail(strict=True, ...)`, the implementation commit removes the marker; each test
  names its requirement in its docstring. A requirement's text stays at 500 characters or less.
- Run `scripts/gate.sh` before each commit and check its exit status directly, never through a pipe;
  chain `git add` and `git commit` with `&&`.
- Commit on `main` and push it (decision A1, pre-authorized). Ask first for tags, releases, PyPI,
  repository settings, deleting branches and force pushes. Never commit real IDs, account numbers
  or tokens as defaults; never print a token.
- Work in the main session, without subagents (the owner's preference).

## How to work

- OpenSpec is not installed globally: `OPENSPEC_TELEMETRY=0 npx --yes @fission-ai/openspec@1.14.1
  <command> </dev/null`.
- Per change: `new change <name>`; proposal, design, tasks and spec deltas; `validate <name>
  --strict`; commit; the xfail tests' commit; the implementation's commit; push; `gh run watch <id>
  --exit-status`; `archive <name> --yes`; `validate --all --strict`; a docs commit.
- Releases: README, "Releasing" (both `pyproject.toml` versions, `uv lock`, a signed `v*` tag). A
  tag builds both distributions, the image `ghcr.io/xinshoutw/xincord` (public) and the GitHub
  Release; from 1.0.0 it also publishes to PyPI through the environments `pypi` and `pypi-plugins`
  (trusted publishers registered, LICENSE in both distributions). Latest: `v0.3.1`.

## Running it

`compose.yaml` runs the published image from a directory of its own: an operator needs only
`compose.yaml` and `.env`; `config.yaml` and `plugins/` sit next to them, the database in the
`<directory>_data` volume, the Lavalink node's config inline (profile `music`). A clone builds the
image with `docker compose -f compose.yaml -f compose.build.yaml up -d --build`.

Test environment: the owner's Mac runs this clone that way, `config.yaml` and `plugins/` at the
repository root (gitignored), with the owner's test application and guild `xincord-test`
(application 1558847245061849158, guild 1558859846730776706, the owner 810822763601461318); its
`.env` needs `XINCORD_TOKEN` and, for MusicPlayer, `COMPOSE_PROFILES=music`.

## Production

- Host: SSH alias `xs-mac` (an Apple M4 Pro Mac with OrbStack). Its SSH config runs a remote
  command with a TTY: use `ssh -o RemoteCommand=none -o RequestTTY=no xs-mac '...'`, with
  `/usr/local/bin` on `PATH` for docker. Redact tokens and keys from anything printed there.
- Both bots, their plugins, tokens and the daily backup: `docs/owner-review.md`, "Production".
  Each runs the `compose.yaml` of its release tag with `XINCORD_VERSION` set to it (0.3.1 since
  2026-10-12);
  compose projects `xincord` and `xincord-shirotsuki`, volumes `<project>_data`.
- To update: copy `compose.yaml` from the new tag, set `XINCORD_VERSION` in `.env`, then
  `docker compose pull && docker compose up -d` in each directory, and check `docker compose logs
  bot` for the plugins' load lines and READY.
- The one-off migration's scripts, its runbook `CUTOVER.md` and copies of the data are in
  `~/selfhost/Discord/xincord-migration/`, outside the repository; the copies go after 2026-10-15
  (#8). Calls to Discord's REST API as a bot ran inside its container with a script that never
  prints the token (`xincord-migration/scripts/dapi.py`); it reads `/bot/config.yaml`, whose token
  is empty since 0.3.0, so make it read `XINCORD_TOKEN` before using it again.

## Next steps

1. PyPI's first release, 1.0.0, when the owner says so.
2. Issues: #3 (youtube-source back to a release that holds its TV client fix), #2 (CustomCommands'
   features left out), #7 (backups to Google Drive), #8 (delete the migration's copies).
3. The follow-ups in `docs/owner-review.md`: the plugins not enabled in production, Renovate's
   first PRs, what to watch.
