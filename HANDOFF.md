# HANDOFF: xincord

Updated 2026-10-12. Read this, then `AGENTS.md` and `docs/porting/decisions.md`: the decisions are
accepted and binding; do not re-open them without asking the owner. Talk to the owner in
Traditional Chinese; everything written into the repository is English.

## State

xincord is the Python 3.14 + uv port of XsDiscordBotKt (Kotlin, JDA). Core and all 18 in-scope
plugins are ported, specified with OpenSpec and tested first (coverage 100%). Since 2026-10-12 both
of the owner's production bots run xincord (below). What waits for the owner is in
`docs/porting/owner-review.md`; details of the build are in `docs/architecture.md`, hard-won facts
in `docs/pitfalls.md`, v3's differences in `docs/porting-guide.md`, and each change's decisions in
`openspec/changes/archive/*/design.md`.

## Where things are

| What | Where |
|---|---|
| This project | `/Users/xinshou/IdeaProjects/xincord`, branch `main`, public at `github.com/xinshoutw/xincord` |
| Kotlin baseline (v3) | `/Users/xinshou/IdeaProjects/XsDiscordBotKt` at `3a59607` |
| Decisions, rules | `docs/porting/decisions.md`, `AGENTS.md` (no CLAUDE.md on purpose) |
| Specs | `openspec/specs/`, active changes in `openspec/changes/` |
| Per-plugin inventories of v3 | `docs/porting/analysis/inventory/<Plugin>.md` |
| Owner's open items | `docs/porting/owner-review.md` |

## Rules (AGENTS.md has them all)

- Replies to the owner in Traditional Chinese; repository content in English; no CJK in `*.py`;
  commit messages ASCII, Conventional Commits (scopes `core`, `build`, `ci`, `docs`,
  `plugin-<name>`), GPG-signed, without attribution lines.
- Code changes go through OpenSpec and xfail-first tests: the failing test is committed with
  `@pytest.mark.xfail(strict=True, ...)`, the implementation commit removes the marker; each test
  names its requirement in its docstring. A requirement's text stays at 500 characters or less.
- Run `scripts/gate.sh` before each commit and check its exit status directly, never through a pipe;
  chain `git add` and `git commit` with `&&`.
- Pushing `main` is pre-authorized. Ask first for tags, releases, PyPI, repository settings, deleting
  branches and force pushes. Never commit real IDs, account numbers or tokens as defaults; never
  print a token.
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
  (trusted publishers registered, LICENSE in both distributions). Latest: `v0.2.2`.

## Running it

`compose.yaml` runs the published image from a directory of its own (`compose-without-clone`): an
operator needs only `compose.yaml` and `.env`; `config.yaml` and `plugins/` sit next to them, the
database in the `<directory>_data` volume, the Lavalink node's config inline. A clone builds the
image with `docker compose -f compose.yaml -f compose.build.yaml up -d --build`.

Test environment: the owner's Mac runs this clone that way, `config.yaml` and `plugins/` at the
repository root (gitignored), with the owner's test application and guild `xincord-test`
(application 1558847245061849158, guild 1558859846730776706, the owner 810822763601461318).

## Production (cut over on 2026-10-12)

- Host: SSH alias `xs-mac` (an Apple M4 Pro Mac with OrbStack). Its SSH config runs a remote
  command with a TTY: use `ssh -o RemoteCommand=none -o RequestTTY=no xs-mac '...'`, with
  `/usr/local/bin` on `PATH` for docker.
- Main bot: `~/selfhost/Discord/xincord`, `compose.yaml` from `main` with the image `0.2.2`
  (`XINCORD_VERSION`), compose project `xincord`, volume `xincord_data`; plugins AutoRole, Calculator, BotInfo, ChatLogger, DynamicVoiceChannel, Economy,
  UptimeHeartbeat, MusicPlayer, NtustAnnouncements, Ticket and VoiceLogger. `.env` holds the node's
  password, `TZ=Asia/Taipei`, YouTube's OAuth refresh token (a spare account) and
  `COMPOSE_PROFILES=music`.
- Shop bot (`shirotsuki`): `~/selfhost/Discord/xincord-shirotsuki`, the same layout and image
  without the node; Economy, UptimeHeartbeat and TicketAwayNotice.
- Both moved to this layout on 2026-10-12; their former clones are `<directory>.clone`, the
  rollback (`xincord-migration/scripts/relayout.sh <name> --rollback`).
- v3's directories (`~/selfhost/Discord/MainServer`, `~/selfhost/Discord/shirotsuki`) stay untouched
  for a rollback. The one-off migration's scripts, its runbook `CUTOVER.md` and copies of the data
  are in `~/selfhost/Discord/xincord-migration/`, outside the repository.
- Calls to Discord's REST API as a bot run inside its container with a script that reads the token
  from `/bot/config.yaml` and never prints it (`xincord-migration/scripts/dapi.py`).

## Next steps

1. The owner's review items of 2026-10-12, in progress: compose without a TTY and the node in
   the `music` profile (done, deployed), the image built in CI, the plugins pinned to their
   core, the token from `XINCORD_TOKEN`, an online backup. Code changes reach production with
   the next release (the owner approves it), the plain log lines included.
2. PyPI's first release, 1.0.0, when the owner says so.
3. Issues: #3 (youtube-source back to a release that holds its TV client fix), #2 (CustomCommands'
   features left out).
4. The follow-ups in `docs/porting/owner-review.md`: the plugins not enabled in production,
   Renovate not running yet, cleaning up the migration's copies after a few days, what to watch.
