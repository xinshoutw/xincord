# Runtime libraries for the Python 3.14 + discord.py port (research snapshot 2026-10-08)

Context: porting a Kotlin/JDA 6 Discord bot (music player, MongoDB, YAML config/i18n, Google Sheets,
Ktor dashboard, interactive console) to Python 3.14 + discord.py under AGPL-3.0.

## 0. Method and conventions

- Package facts come from the PyPI JSON API (`https://pypi.org/pypi/<name>/json`), fetched 2026-10-08.
  "Released" = upload time of the first file of that version.
- "cp314" counts GIL-build wheels tagged `cp314-cp314`; "cp314t" counts free-threaded wheels;
  "abi3" wheels (e.g. `cp38-abi3`) also install on GIL CPython 3.14 but not on 3.14t.
- Pure-Python packages are marked "pure"; for them 3.14 support is only "declared" (classifier) or "not declared".
- Changelogs, pyprojects and source were read from GitHub at the named tag/commit.
- Items marked **UNCONFIRMED** could not be verified from a primary source.

## 1. Master table (PyPI, 2026-10-08)

| Package | Version | Released | requires_python | Wheels (3.14) | License (PyPI) | 3.1x classifiers |
|---|---|---|---|---|---|---|
| [discord.py](https://pypi.org/project/discord.py/2.7.1/) | 2.7.1 | 2026-03-03 | `>=3.8` | pure (py3-none-any) | MIT License | 3.10,3.11,3.12 |
| [aiohttp](https://pypi.org/project/aiohttp/3.14.4/) | 3.14.4 | 2026-10-05 | `>=3.10` | cp314 x23, cp314t x18 | Apache-2.0 AND MIT | 3.10,3.11,3.12,3.13,3.14 |
| [audioop-lts](https://pypi.org/project/audioop-lts/0.2.2/) | 0.2.2 | 2025-08-05 | `>=3.13` | cp314 x0, cp314t x16, abi3 x16 | PSF-2.0 | 3.13,3.14 |
| [PyNaCl](https://pypi.org/project/PyNaCl/1.6.2/) | 1.6.2 | 2026-01-01 | `>=3.8` | cp314 x0, cp314t x12, abi3 x12 | Apache Software License | 3.10,3.11,3.12,3.13,3.14 |
| [PyNaCl](https://pypi.org/project/PyNaCl/1.5.0/) | 1.5.0 | 2022-01-07 | `>=3.6` | abi3 x9 | Apache License 2.0 | 3.10 |
| [davey](https://pypi.org/project/davey/0.1.6/) | 0.1.6 | 2026-06-22 | `>=3.8` | cp314 x14, cp314t x10 | MIT License | 3.10,3.11,3.12,3.13 |
| [discord-ext-voice-recv](https://pypi.org/project/discord-ext-voice-recv/0.5.2a179/) | 0.5.2a179 | 2025-06-18 | `>=3.8` | pure (py3-none-any) | MIT License | 3.10,3.11,3.12 |
| [discord-ext-songbird](https://pypi.org/project/discord-ext-songbird/0.5.0/) | 0.5.0 | 2026-05-28 | `>=3.14` | cp314 x7, cp314t x7 | MIT License | 3.14 |
| [yt-dlp](https://pypi.org/project/yt-dlp/2026.8.19/) | 2026.8.19 | 2026-08-19 | `>=3.10` | pure (py3-none-any) | Unlicense | 3.10,3.11,3.12,3.13,3.14 |
| [yt-dlp-ejs](https://pypi.org/project/yt-dlp-ejs/0.8.0/) | 0.8.0 | 2026-03-17 | `>=3.10` | pure (py3-none-any) | Unlicense AND MIT AND ISC | 3.10,3.11,3.12,3.13,3.14 |
| [deno](https://pypi.org/project/deno/2.9.7/) | 2.9.7 | 2026-09-17 | `>=3.10` | platform wheels, no cp314 | MIT | - |
| [wavelink](https://pypi.org/project/wavelink/3.5.2/) | 3.5.2 | 2026-04-23 | `>=3.10` | pure (py3-none-any) | MIT License | 3.10,3.11,3.12 |
| [mafic](https://pypi.org/project/mafic/2.11.0/) | 2.11.0 | 2026-03-19 | `<4.0,>=3.8` | pure (py3-none-any) | MIT License | 3.10,3.11,3.12,3.13,3.14 |
| [pomice](https://pypi.org/project/pomice/2.11.0/) | 2.11.0 | 2026-03-01 | `>=3.8` | pure (py3-none-any) | GPL | - |
| [lavalink](https://pypi.org/project/lavalink/5.11.1/) | 5.11.1 | 2026-10-06 | `(none)` | sdist only | ? | - |
| [sonolink](https://pypi.org/project/sonolink/1.4.0/) | 1.4.0 | 2026-09-16 | `>=3.12` | pure (py3-none-any) | MIT | 3.12,3.13,3.14 |
| [pymongo](https://pypi.org/project/pymongo/4.18.2/) | 4.18.2 | 2026-09-24 | `>=3.9` | cp314 x10, cp314t x10 | Apache-2.0 | 3.10,3.11,3.12,3.13,3.14 |
| [motor](https://pypi.org/project/motor/3.7.1/) | 3.7.1 | 2025-05-14 | `>=3.9` | pure (py3-none-any) | Apache Software License | 3.10,3.11,3.12,3.13 |
| [mongomock](https://pypi.org/project/mongomock/4.3.0/) | 4.3.0 | 2024-11-16 | `(none)` | pure (py3-none-any) | ISC License (ISCL) | 3.10,3.11,3.12 |
| [mongomock-ng](https://pypi.org/project/mongomock-ng/7.11.1/) | 7.11.1 | 2026-07-24 | `>=3.10` | pure (py3-none-any) | ISC License (ISCL) | 3.10,3.11,3.12,3.13,3.14 |
| [mongomock-motor](https://pypi.org/project/mongomock-motor/0.0.36/) | 0.0.36 | 2025-05-16 | `<4.0,>=3.8` | pure (py3-none-any) | MIT License | 3.10,3.11,3.12,3.13 |
| [testcontainers](https://pypi.org/project/testcontainers/4.15.0/) | 4.15.0 | 2026-07-24 | `>=3.10` | pure (py3-none-any) | Apache-2.0 | 3.10,3.11,3.12,3.13,3.14 |
| [pymongo_inmemory](https://pypi.org/project/pymongo_inmemory/0.5.0/) | 0.5.0 | 2025-03-13 | `<4.0,>=3.9` | pure (py3-none-any) | MIT License | 3.10,3.11,3.12,3.13 |
| [pytest-mongo](https://pypi.org/project/pytest-mongo/5.0.0/) | 5.0.0 | 2026-09-09 | `>=3.11` | pure (py3-none-any) | LGPL-3.0-or-later | 3.11,3.12,3.13,3.14,3.15 |
| [SecantusDB](https://pypi.org/project/SecantusDB/0.7.0b2/) | 0.7.0b2 | 2026-10-08 | `>=3.10` | platform wheels, no cp314 | GPL-2.0-only AND CC-BY-4.0 | - |
| [montydb](https://pypi.org/project/montydb/2.5.6/) | 2.5.6 | 2025-11-01 | `>=3.7` | pure (py3-none-any) | BSD License, Other/Proprietary License | 3.10,3.11,3.12 |
| [aiosqlite](https://pypi.org/project/aiosqlite/0.22.1/) | 0.22.1 | 2025-12-23 | `>=3.9` | pure (py3-none-any) | MIT License | - |
| [SQLAlchemy](https://pypi.org/project/SQLAlchemy/2.1.4/) | 2.1.4 | 2026-10-07 | `>=3.11` | cp314 x10, cp314t x10 | MIT | 3.11,3.12,3.13,3.14,3.15 |
| [SQLAlchemy](https://pypi.org/project/SQLAlchemy/2.0.54/) | 2.0.54 | 2026-09-15 | `>=3.7` | cp314 x7, cp314t x7 | MIT | 3.10,3.11,3.12,3.13,3.14,3.15 |
| [pydantic](https://pypi.org/project/pydantic/2.13.5/) | 2.13.5 | 2026-08-28 | `>=3.9` | pure (py3-none-any) | MIT | 3.10,3.11,3.12,3.13,3.14 |
| [pydantic_core](https://pypi.org/project/pydantic_core/2.46.5/) | 2.46.5 | 2026-08-28 | `>=3.9` | cp314 x15, cp314t x15 | MIT | 3.10,3.11,3.12,3.13,3.14 |
| [pydantic_core](https://pypi.org/project/pydantic_core/2.49.0/) | 2.49.0 | 2026-09-09 | `>=3.10` | cp314 x16, cp314t x15 | MIT | 3.10,3.11,3.12,3.13,3.14 |
| [pydantic-settings](https://pypi.org/project/pydantic-settings/2.15.0/) | 2.15.0 | 2026-08-07 | `>=3.10` | pure (py3-none-any) | MIT | 3.10,3.11,3.12,3.13,3.14 |
| [msgspec](https://pypi.org/project/msgspec/0.22.0/) | 0.22.0 | 2026-09-29 | `>=3.10` | cp314 x11, cp314t x10 | BSD-3-Clause | 3.10,3.11,3.12,3.13,3.14,3.15 |
| [PyYAML](https://pypi.org/project/PyYAML/6.0.3/) | 6.0.3 | 2025-09-25 | `>=3.8` | cp314 x9, cp314t x9 | MIT License | 3.10,3.11,3.12,3.13,3.14 |
| [ruamel.yaml](https://pypi.org/project/ruamel.yaml/0.19.1/) | 0.19.1 | 2026-01-02 | `>=3.9` | pure (py3-none-any) | MIT License | 3.10,3.11,3.12,3.13,3.14 |
| [ruamel.yaml.clib](https://pypi.org/project/ruamel.yaml.clib/0.2.15/) | 0.2.15 | 2025-11-16 | `>=3.9` | cp314 x10, cp314t x0 | MIT License | 3.10,3.11,3.12,3.13,3.14 |
| [ruamel.yaml.clibz](https://pypi.org/project/ruamel.yaml.clibz/0.3.7/) | 0.3.7 | 2026-01-02 | `>=3.9` | sdist only | MIT | - |
| [strictyaml](https://pypi.org/project/strictyaml/1.7.3/) | 1.7.3 | 2023-03-10 | `>=3.7.0` | pure (py3-none-any) | MIT License | - |
| [ruyaml](https://pypi.org/project/ruyaml/0.91.0/) | 0.91.0 | 2021-12-07 | `>=3.6` | pure (py3-none-any) | MIT License | 3.10 |
| [yaml-rs](https://pypi.org/project/yaml-rs/0.1.6/) | 0.1.6 | 2026-07-07 | `>=3.10` | cp314 x21, cp314t x20 | Unlicense | 3.10,3.11,3.12,3.13,3.14,3.15 |
| [prompt_toolkit](https://pypi.org/project/prompt_toolkit/3.0.53/) | 3.0.53 | 2026-07-26 | `>=3.10` | pure (py3-none-any) | BSD License | 3.10,3.11,3.12,3.13,3.14 |
| [rich](https://pypi.org/project/rich/15.0.0/) | 15.0.0 | 2026-04-12 | `>=3.9.0` | pure (py3-none-any) | MIT License | 3.10,3.11,3.12,3.13,3.14 |
| [gspread](https://pypi.org/project/gspread/6.2.1/) | 6.2.1 | 2025-05-14 | `>=3.8` | pure (py3-none-any) | MIT License | 3.10,3.11 |
| [gspread-asyncio](https://pypi.org/project/gspread-asyncio/3.0.0/) | 3.0.0 | 2026-08-30 | `>=3.11` | pure (py3-none-any) | MIT License | - |
| [google-auth](https://pypi.org/project/google-auth/2.61.0/) | 2.61.0 | 2026-10-07 | `>=3.10` | pure (py3-none-any) | Apache Software License | 3.10,3.11,3.12,3.13,3.14,3.15 |
| [google-auth-oauthlib](https://pypi.org/project/google-auth-oauthlib/1.5.0/) | 1.5.0 | 2026-09-29 | `>=3.10` | pure (py3-none-any) | Apache Software License | 3.10,3.11,3.12,3.13,3.14,3.15 |
| [fastapi](https://pypi.org/project/fastapi/0.142.4/) | 0.142.4 | 2026-10-07 | `>=3.10` | pure (py3-none-any) | MIT | 3.10,3.11,3.12,3.13,3.14 |
| [starlette](https://pypi.org/project/starlette/1.7.0/) | 1.7.0 | 2026-09-23 | `>=3.10` | pure (py3-none-any) | BSD-3-Clause | 3.10,3.11,3.12,3.13,3.14,3.15 |
| [litestar](https://pypi.org/project/litestar/2.24.0/) | 2.24.0 | 2026-06-11 | `<4.0,>=3.8` | pure (py3-none-any) | MIT License | 3.10,3.11,3.12,3.13,3.14 |
| [uvicorn](https://pypi.org/project/uvicorn/0.54.0/) | 0.54.0 | 2026-09-25 | `>=3.10` | pure (py3-none-any) | BSD-3-Clause | 3.10,3.11,3.12,3.13,3.14 |
| [httpx](https://pypi.org/project/httpx/0.28.1/) | 0.28.1 | 2024-12-06 | `>=3.8` | pure (py3-none-any) | BSD License | 3.10,3.11,3.12 |
| [httpx2](https://pypi.org/project/httpx2/2.13.1/) | 2.13.1 | 2026-09-23 | `>=3.10` | pure (py3-none-any) | BSD-3-Clause | 3.10,3.11,3.12,3.13,3.14,3.15 |
| [beautifulsoup4](https://pypi.org/project/beautifulsoup4/4.15.0/) | 4.15.0 | 2026-06-07 | `>=3.7.0` | pure (py3-none-any) | MIT License | - |
| [selectolax](https://pypi.org/project/selectolax/1.0.0/) | 1.0.0 | 2026-10-03 | `<3.16,>=3.9` | cp314 x9, cp314t x9 | MIT | 3.10,3.11,3.12,3.13,3.15 |
| [lxml](https://pypi.org/project/lxml/6.1.3/) | 6.1.3 | 2026-09-02 | `>=3.8` | cp314 x18, cp314t x18 | BSD-3-Clause | 3.10,3.11,3.12,3.13,3.14,3.15 |
| [babel](https://pypi.org/project/babel/2.18.0/) | 2.18.0 | 2026-02-01 | `>=3.8` | pure (py3-none-any) | BSD License | 3.10,3.11,3.12,3.13,3.14 |

Notes on the table:
- `lavalink` (Lavalink.py) uploads only an sdist without metadata; from `setup.py` at tag 5.11.1:
  `install_requires=['aiohttp>=3.9.0,<4']`, no `python_requires`; GitHub license MIT.
- `pomice` PyPI license field is just "GPL"; GitHub reports GPL-3.0.
- `montydb` classifiers list both "BSD License" and "Other/Proprietary License"; GitHub reports BSD-3-Clause.
- `audioop-lts` and `PyNaCl` 1.6.x ship `abi3` wheels for GIL 3.14 plus dedicated `cp314t` wheels.
- `selectolax` 1.0.0 ships cp314 wheels but omits the 3.14 classifier.
- SQLAlchemy `[asyncio]` needs `greenlet` (3.5.6, 2026-09-14, cp314 + cp314t wheels, MIT AND PSF-2.0).
  discord.py `[speed]` pulls `orjson` (3.13.0, 2026-10-07, cp314 wheels, no cp314t, MPL-2.0 AND (Apache-2.0 OR MIT)).

---

## 2. discord.py (topic 1)

### Version and Python support
- Latest: **2.7.1, uploaded 2026-03-03** (PyPI). No release since; `master` has unreleased commits up to
  2026-09-01 ("Reconnect the gateway with the default URL during 500s").
  Release history: 2.5.0 2025-02-18, 2.6.0 2025-08-18, 2.6.4 2025-10-08, 2.7.0 2026-02-27, 2.7.1 2026-03-03.
  Source: https://pypi.org/pypi/discord.py/json ; https://github.com/Rapptz/discord.py/commits/master
- `requires-python = ">=3.8"`; classifiers stop at 3.12, but CI runs `['3.8', '3.x']`
  (https://github.com/Rapptz/discord.py/blob/v2.7.1/.github/workflows/test.yml), and the changelog carries
  3.14-specific fixes: 2.6.4 "Use `compression.zstd` from the standard library if available on Python 3.14",
  2.7.0 "Fix flag annotations not working under Python 3.14" and "Don't assume Python 3.14 always has
  `compression.zstd`". So 3.14 is effectively supported but not declared in metadata.

### Dependencies at tag v2.7.1
(https://github.com/Rapptz/discord.py/blob/v2.7.1/requirements.txt, .../pyproject.toml)
- core: `aiohttp>=3.7.4,<4`, `audioop-lts; python_version>='3.13'`
- `[voice]`: `PyNaCl>=1.5.0,<1.6`, `davey>=0.1.0`
- `[speed]`: `orjson>=3.5.4`, `aiodns>=1.1` (non-Windows), `Brotli`, `zstandard>=0.23.0; python_version <= '3.13'`
- On `master` (unreleased, commit 5d74ed3e 2026-03-14 "Bump PyNaCl version to allow 1.6.x version installs"):
  `PyNaCl>=1.6.0,<1.7`.
- Consequence on 3.14 today: `discord.py[voice]` resolves PyNaCl **1.5.0 (2022-01-07, `cp36-abi3` wheels)**,
  fine for GIL CPython 3.14, no free-threaded wheels. davey 0.1.6 has cp314 wheels for macOS x86_64/arm64,
  manylinux (x86_64, aarch64, armv7l, i686, ppc64le, s390x), musllinux, win32, win_amd64; its cp314t wheels
  are Linux-only. Free-threaded 3.14t is impractical for voice.

### Changelog highlights since 2.5 (https://github.com/Rapptz/discord.py/blob/master/docs/whats_new.rst)
- **2.6.0 (2025-08-18)**
  - Components V2 through `ui.LayoutView` (manual layout). New components: `ui.Section`, `ui.TextDisplay`,
    `ui.Thumbnail`, `ui.MediaGallery`, `ui.File`, `ui.Separator`, `ui.Container`, `ui.ActionRow`.
    Backwards compatible, including `ui.DynamicItem`.
  - Modal improvements, phase 1: `ui.Select` inside modals and `ui.Label` (versionadded 2.6). `TextInput.label`
    becomes optional and is deprecated in favour of `Label`.
  - Guild tags (`PrimaryGuild`), new pins endpoint (`abc.Messageable.pins` becomes an async iterator; awaiting
    it is deprecated), onboarding, `Locale.language_code`, `Interaction.filesize_limit`, gradient role colours.
  - "Fix voice connection issues and upgrade the voice version to 8."
- **2.6.1 to 2.6.4**: fixes for Section/LayoutView/DynamicItem, modal submit with selects, the `required` kwarg on selects.
- **2.7.0 (2026-02-27)**
  - **DAVE protocol support for voice (#10300; PR merged 2026-01-07).**
  - New modal components: `ui.CheckboxGroup`, `ui.Checkbox`, `ui.RadioGroup` (+ option classes).
  - `ui.FileUpload` (docstring `versionadded:: 2.7`): file_upload.py was added on master 2025-09-21
    (commit 2d7e0614) and first ships in the v2.7.0 tag. The changelog does not mention it.
  - `app_commands.Timestamp` / `commands.Timestamp` converter, new permissions (`bypass_slowmode`,
    `set_voice_channel_status`, `pin_messages`), `User.collectibles`.
  - "Fix FFmpeg errors not sent to after callback", "Allow `ui.View` initialization without a running event loop".
- **2.7.1 (2026-03-03)**: LayoutView memory-leak fix, aiohttp websocket-timeout deprecation fix, prints the `davey`
  version in `python -m discord --version`, and "Raise an error and warn when `davey` is not installed and using voice".
- Unreleased on master (2026-04 to 2026-09): selects default `required=True` (dae01425), heartbeat latency race fix,
  nested UI parent state fix, file upload limit validation.

### DAVE in discord.py
Source: https://github.com/Rapptz/discord.py/blob/v2.7.1/discord/voice_state.py, voice_client.py, gateway.py
- Implemented with **`davey`** (Snazzah's Rust/OpenMLS DAVE implementation, PyO3 bindings, MIT;
  https://github.com/Snazzah/davey, py-0.1.6 released 2026-06-22).
- Identify sends `max_dave_protocol_version = davey.DAVE_PROTOCOL_VERSION`. The voice websocket handles
  opcodes 21–31 (prepare/execute transition, prepare epoch, MLS external sender/key package/proposals/
  commit-welcome/announce-commit/welcome/invalid-commit) and passthrough mode during transitions.
- Outgoing Opus frames are E2EE-encrypted with `dave_session.encrypt_opus()` before transport encryption.
  `VoiceClient.voice_privacy_code` (2.7) exposes the privacy code.
- **In 2.7.1, `VoiceClient.__init__` raises `RuntimeError('davey library needed in order to use voice')`** when
  davey is missing, so `discord.py[voice]` is mandatory.
- Limitations:
  - Send-only. discord.py has no voice receive API (RFC #1094 still open since 2018-02-20), so no decrypt path.
  - The check lives in `VoiceClient`. Custom `VoiceProtocol` implementations such as Lavalink players
    (e.g. `wavelink.Player(discord.VoiceProtocol)`) do not need davey in the bot process; the Lavalink server does DAVE.
  - Free-threaded 3.14t is hampered by PyNaCl 1.5.0 (abi3 only) and davey's Linux-only cp314t wheels.
  - Open issue #10520 (2026-09-15): an initial handshake failure in `connect()` is masked by an AttributeError and kills the retry loop.

### Voice receive status
- discord.py: not supported (see above).
- `discord-ext-voice-recv` 0.5.2a179 (alpha, 2025-06-18; last commit 2025-06-18) predates DAVE.
  - Issue #53 (opened 2026-03-03, open): Opus decodes to gibberish after upgrading to 2.7.1.
  - Issue #64 (opened 2026-08-18, open): feature request to add DAVE packet decryption.
  - Issue #61 (closed): "DAVE not decrypted on receive path".
  - Effectively **broken for E2EE calls**: https://github.com/imayhaveborkedit/discord-ext-voice-recv/issues
- `discord-ext-songbird` 0.5.0 (2026-05-28, beta, MIT, requires Python >=3.14, cp314/cp314t wheels, 7 GitHub stars)
  replaces discord.py's voice backend with Rust Songbird 0.6.0 and has receive APIs. Its Cargo.lock includes
  the `davey` 0.1.3 crate, so it is **probably** DAVE-capable. **UNCONFIRMED.**

---

## 3. Discord DAVE (E2EE A/V) requirement for bots (topic 2)

| Date | Event | Source |
|---|---|---|
| 2024-09-17 | DAVE docs + voice opcodes published. "Not immediately required"; promise of ≥6 months notice before sunsetting non-E2EE | Discord change log, https://docs.discord.com/developers/change-log (source: github.com/discord/discord-api-docs `developers/change-log.mdx`) |
| 2025-09-02 | Change log "Deprecating Non-E2EE Voice Calls": "only support E2EE calls starting on **March 1st, 2026**" for DMs, GDMs, voice channels, Go Live; non-DAVE clients/apps "will no longer be able to participate" | same change log; voice docs warning https://docs.discord.com/developers/topics/voice-connections#end-to-end-encryption-dave-protocol (still says March 1st) |
| 2026-01-29 (edited 2026-02-20, updated 2026-10-05) | Support article: "Starting **March 2nd, 2026**… will require end-to-end encryption support"; FAQ: "Third-party applications and bots that connect to Discord voice must implement DAVE support to continue functioning after March 2, 2026." | https://support.discord.com/hc/en-us/articles/38025123604631 (via Zendesk API) |
| **2026-03-02 12:02 PST** | Status incident "A/V E2EE Enforcement for Non-stage Voice Calls": DAVE-capable clients "are now required to connect to non-stages voice calls… the voice gateway will reject your connection with close code **4017**". Resolved 2026-03-11 | https://discordstatus.com/incidents/k22tny62jcw3 (via `/api/v2/incidents.json`) |
| 2026-03-02 (edited 2026-03-03, updated 2026-09-16) | Support article with the same 4017 wording | https://support.discord.com/hc/en-us/articles/38749827197591 |
| 2026-05-18 | Blog "Every Voice and Video Call on Discord Is Now End-to-End Encrypted": migration completed early March 2026; **stage channels are the one exception**; Discord is "removing the client code that supports unencrypted fallback" | https://discord.com/blog/every-voice-and-video-call-on-discord-is-now-end-to-end-encrypted |

- Close code table: `4017 | E2EE/DAVE protocol required`
  (https://docs.discord.com/developers/topics/opcodes-and-status-codes#voice).
- **Status at 2026-10-08:** DAVE has been mandatory for non-stage voice (DM/GDM/voice channels/Go Live) since 2026-03-02.
  A bot without DAVE gets 4017. Developer docs still show "March 1st"; the operational cutover was March 2.
- Inference, not a sourced bot-specific statement: stage channels are exempt, so non-DAVE stage connections may still work.

---

## 4. Music stack options (topic 3)

### (a) discord.py voice + FFmpeg + yt-dlp
- **yt-dlp 2026.08.19** (GitHub release and PyPI 2026-08-19). Requires Python >=3.10 (README: CPython 3.10+), Unlicense.
  - The PyInstaller executables are GPLv3+ (README). The PyPI package is not.
  - Nightly `.devN` builds are on PyPI up to 2026.9.27.232945.dev0.
  - Release notes: https://github.com/yt-dlp/yt-dlp/releases/tag/2026.08.19 (adds `visionos` client and `web_embedded` fallbacks, removes `android_vr` from defaults).
- **External JS runtime is now required for full YouTube support** (README "Strongly recommended"; wiki EJS page,
  https://github.com/yt-dlp/yt-dlp/wiki/EJS, wiki snapshot 2026-09-27):
  - YouTube JS challenges are solved by `yt-dlp-ejs` scripts running in an external runtime. `pip install "yt-dlp[default]"`
    pins `yt-dlp-ejs==0.8.0` (released 2026-03-17; Unlicense AND MIT AND ISC). Alternatively `--remote-components ejs:npm|ejs:github`.
  - Runtimes:
    - **deno**: recommended, the only one enabled by default, minimum 2.3.0.
    - node: ≥22.0.0, enable with `--js-runtimes node`.
    - quickjs / quickjs-ng: enable with `--js-runtimes quickjs`.
    - bun: deprecated, ≤1.3.14 only.
  - The `yt-dlp[deno]` extra installs `deno>=2.6.6` from PyPI (deno 2.9.7, 2026-09-17, MIT). Wheels cover macOS x86_64/arm64,
    manylinux_2_27 x86_64/aarch64 and win_amd64. There is **no musl wheel**, so Alpine images need a system deno.
  - README `player_client`: the default is `visionos,web`; "If no JavaScript runtime/engine is available, then `web` is omitted."
- **PO tokens** (wiki PO Token Guide):
  - A GVS PO token is required for `web`, `mweb`, `web_music`, `web_creator` and `tv_simply`; for `android` and `ios`, either a GVS or a Player PO token is required.
  - Not required for `tv`, `web_embedded` (embeddable videos only) or `android_vr`.
  - Tokens are bound to the video ID, so the guide recommends a provider plugin (`bgutil-ytdlp-pot-provider`, `yt-dlp-getpot-wpc`) over manual tokens.
  - The YouTube wiki notice says "YouTube is gradually enforcing" PO tokens.
- **SABR**: the PO guide states the `web` client has "Only SABR formats available", and `tv` does "in some cases".
  Tracking issue #12482 "[youtube] `web` only has SABR formats" is open (created 2025-02-26, last updated 2026-08-18).
  Age-restricted downloads are a recurring problem (open issues #17542, #17751, #17397 updated Sept to Oct 2026).
- discord.py side: `FFmpegOpusAudio` (ffmpeg binary on PATH) outputs Opus and skips library encoding.
  `FFmpegPCMAudio` needs libopus loaded (discord/player.py, v2.7.1).

### (b) Lavalink v4
- **Lavalink 4.2.2 (2026-03-06)** is the latest release (https://github.com/lavalink-devs/Lavalink/releases).
  - **4.2.0 (2026-02-28) is "the first Lavalink release with DAVE (E2EE voice) support."** It uses koe 3.0.0-pre and libdave-jvm; 4.2.2 moves to koe 3.0.0-pre6 and libdave 0.1.3.
  - Client libraries must send the new **`channelId`** in the voice state.
  - Requirement: Java 17+ (README).
  - YouTube needs the `youtube-source` plugin, latest 1.18.2 (2026-07-27, MIT). It offers OAuth, poToken and remote-cipher-server workarounds (its README).
- Lavalink's own client list marks DAVE support per client (https://github.com/lavalink-devs/Lavalink/blob/master/docs/clients.md;
  last related edits 2026-04-11 "fix wavelink dave support", 2026-05-16 "add SonoLink", 2026-08-25).
  It marks wavelink, mafic, pomice, lavalink.py, SonoLink, hikari-ongaku, lavaplay.py and lavalink-rs as DAVE ✅.

| Client | Latest (date) | DAVE since | discord.py compat | Python | License | Maintenance signal |
|---|---|---|---|---|---|---|
| wavelink | 3.5.2 (2026-04-23) | 3.5.1 (2026-04-11) "Adds DAVE support"; sends `channelId` | `discord.py>=2.7.0` (PyPI requires_dist); `Player(discord.VoiceProtocol)` | >=3.10 (classifiers ≤3.12) | MIT | PythonistaGuild, 408★, last push 2026-07-23; 2-year gap 2024-07 to 2026-04 |
| mafic | 2.11.0 (2026-03-19) | 2.11.0 "include channelId in voice state updates for Lavalink 4.2.x" | discord.py v2 / nextcord / disnake / py-cord | >=3.8,<4 (classifiers to 3.14) | MIT | 75★, low cadence (previous release 2025-04/05) |
| pomice | 2.11.0 (2026-03-01) | 2.11.0 "include `channel_id`… for Lavalink >=4.2.0" | discord.py v2 (no pin) | >=3.8 (classifier 3.8 only) | **GPL-3.0** | 84★ |
| lavalink.py | 5.11.1 (2026-10-06) | 5.10.0 (2026-02-28) "support for DAVE-enabled Lavalink builds by sending `channelId`" | library-agnostic | not declared | MIT | 243★, most recently active |
| SonoLink | 1.4.0 (2026-09-16) | ✅ per Lavalink docs (since first listing) | discord.py v2 / py-cord / disnake / nextcord | >=3.12 (to 3.14) | MIT | new (first release 2026-04-11), 31★, msgspec-based |

- Also seen: `revvlink` 1.0.5 (2026-03-16), a wavelink-style fork whose `dave` extra requires `davey>=1.0.0`,
  a version that does not exist on PyPI (latest 0.1.6), so that extra is uninstallable. Not recommended.

### (c) JDA stack today (for comparison)
- JDA 6.7.0 (GitHub release 2026-09-20; Maven Central). README: "To use JDA for audio connections, you must also
  add a dependency that implements the DAVE Protocol."
- lavaplayer 2.2.7 (2026-07-03, Apache-2.0; `dev.arbjerg:lavaplayer`), youtube-source 1.18.2 (2026-07-27, MIT).
- JDAVE 0.1.8 (Maven Central lastUpdated 2026-03-29): Java bindings to Discord's libdave via the FFM API.
  Requires **Java 25**. Apache-2.0. The README warns it is "still very new and only tested at small scale".
- Takeaway: Python has no in-process lavaplayer equivalent. You either use yt-dlp+FFmpeg in-process with
  the YouTube friction above, or run Lavalink (JVM) and reuse lavaplayer/youtube-source there.

---

## 5. MongoDB (topic 4)

- **PyMongo 4.18.2 (2026-09-24)**, `>=3.9`, Apache-2.0, cp314 ×10 + cp314t ×10 wheels.
  Changelog (https://github.com/mongodb/mongo-python-driver/blob/master/doc/changelog.rst):
  - Async API introduced as **beta in 4.9 (2024-09-18)**; "**The asynchronous API is now stable and no longer in beta**" in **4.13.0 (2025-05-14)**.
  - 4.18.0 (2026-09-03): dropped MongoDB 4.2, added MongoDB 9.0, deprecated PyPy.
  - Unreleased 4.19 adds Python 3.15 and subinterpreter support.
- **Motor 3.7.1 (2025-05-14)** is the last release.
  - Motor README (https://github.com/mongodb/motor): "As of May 14th, 2025, Motor is deprecated… only bug fixes… until it reaches end of life on **May 14th, 2026**. After that, only critical bug fixes… until final support ends on **May 14th, 2027**."
  - The docs banner (https://motor.readthedocs.io/en/stable/) gives the same dates.
  - As of today Motor is past EOL and in critical-fixes-only mode. Migration guide: https://www.mongodb.com/docs/languages/python/pymongo-driver/current/reference/migration/
- Test doubles:
  - **mongomock 4.3.0 (2024-11-16)**, ISC, **sync only**.
    - Async request #916 "Support pymongo async" is open (2025-04-10).
    - "Seeking maintainers" notice added 2025-02-12; last commit 2025-06-30.
  - mongomock-ng 7.11.1 (2026-07-24) is a 3-star fork (ISC, declares 3.14). No `AsyncMongoClient` found in code search. Async support **UNCONFIRMED** and likely absent.
  - mongomock-motor 0.0.36 (2025-05-16) mocks **Motor's** API on top of mongomock (`requires motor>=2.5`).
    It is not a PyMongo-Async fake; open issue #62 "How to migrate away from motor?" (2026-01-21).
  - **No maintained fake for PyMongo's `AsyncMongoClient` was found** (PyPI name probes and GitHub/web search).
- Real-server options:
  - **testcontainers 4.15.0 (2026-07-24)**, Apache-2.0, `>=3.10`, declares 3.14. The `testcontainers[mongodb]` extra pulls `pymongo>=4`.
    In 4.15.0 the module is **`testcontainers.community.mongodb`** (`MongoDbContainer`, default image `mongo:latest`;
    `MongoDBAtlasLocalContainer`). The old `testcontainers.mongodb` import now emits a DeprecationWarning. Needs Docker.
  - pytest-mongo 5.0.0 (2026-09-09, LGPL-3.0-or-later, `>=3.11`, declares 3.14/3.15) provides `mongo_proc`/`mongodb` fixtures.
    It spawns a **locally installed** `mongod`; `mongo_noproc` attaches to an existing server.
  - **pymongo-inmemory 0.5.0 (2025-03-13)** is the closest analog to flapdoodle: it downloads official `mongod` binaries
    from a built-in URL bank and wraps a **sync** `MongoClient`. Inactive since 2025-03-13 with 28 open issues; Python classifiers ≤3.13.
  - **SecantusDB 0.7.0b2 (2026-10-08; first PyPI release 2026-08)** is an in-process or daemon MongoDB *wire-protocol*
    server on WiredTiger ("a surrogate single-node database for your tests"). It is beta, has **no cp314 wheels**
    (cp310 to cp313 only) and is licensed **GPL-2.0-only AND CC-BY-4.0**. A web-search summary mentioned a PyMongo-async
    validation report; **UNCONFIRMED** here.
  - montydb 2.5.6 (2025-11-01): embedded store with a PyMongo-like API. It is not wire-compatible and sync-only.
- **Answer: there is no maintained, async-ready Python equivalent of flapdoodle embed-mongo.** Practical choices are
  testcontainers (Docker), pytest-mongo (local mongod), or a repository-interface fake you write yourself.

## 6. SQLite async (topic 5)
- **aiosqlite 0.22.1 (2025-12-23)**, MIT, `>=3.9`, pure Python. From 0.22.0, `Connection` no longer subclasses `Thread`,
  so you must `await close()` or call `stop()` (CHANGELOG). CI matrix is 3.9–3.13, so **3.14 is not in CI**;
  it is a thin wrapper over stdlib sqlite3 and likely fine. **UNCONFIRMED.**
- **SQLAlchemy 2.1.4 (2026-10-07)**: the 2.1 line went GA with 2.1.0 on 2026-09-24. Requires `>=3.11`, MIT, cp314 + cp314t wheels.
  The maintenance line is **2.0.54 (2026-09-15)**, `>=3.7`, cp314 + cp314t wheels, classifiers to 3.15.
  `[asyncio]` needs greenlet (cp314 ok).

## 7. Validation / config models (topic 6)
- **pydantic 2.13.5 (2026-08-28)**, MIT, `>=3.9`, pins `pydantic-core==2.46.5` (2026-08-28, **cp314 ×15 + cp314t ×15** wheels).
  Pre-release 2.14.0b2 (2026-09-09) uses pydantic-core 2.49.0 (cp314 ×16, cp314t ×15).
- **pydantic-settings 2.15.0 (2026-08-07)**, MIT, `>=3.10`. Its `yaml` extra uses PyYAML (no comment round-trip).
- **msgspec 0.22.0 (2026-09-29)**, BSD-3-Clause, `>=3.10`, cp314 ×11 + cp314t ×10, classifiers 3.14/3.15.
  The project now lives at github.com/msgspec/msgspec. Its YAML support goes through PyYAML.

## 8. YAML (topic 7)
- **PyYAML 6.0.3 (2025-09-25)**, MIT, `>=3.8`, cp314 ×9 + cp314t ×9 wheels. YAML 1.1, no comment preservation.
- **ruamel.yaml 0.19.1 (2026-01-02)**, MIT, `>=3.9`, pure wheel, classifiers to 3.14, "Development Status :: 4 - Beta". This is the comment-preserving round-trip library.
  - From 0.19.1 the package no longer depends on any C extension. Optional `[libyaml]` gives `ruamel.yaml.clibz`, built locally with Zig (sdist only); `[oldlibyaml]` gives `ruamel.yaml.clib` (0.2.15, cp314 but **no cp314t**). Round-trip mode gets no benefit from either.
  - Maintenance: a single maintainer on SourceForge. No release in the 9 months since 2026-01-02.
  - The PyPI description warns that the PEP 625 project-name issue "may make future uploads to PyPI impossible".
    That is a supply-chain risk to pin and watch.
- Other comment-preserving options:
  - strictyaml 1.7.3 (2023-03-10, MIT; vendors ruamel code; restricted YAML subset; repo last push 2025-05-23): effectively dormant.
  - ruyaml 0.91.0 (2021-12-07): dormant fork with no release since.
  - yaml-rs 0.1.6 (2026-07-07, Unlicense, cp314/cp314t) is a fast Rust parser. Its README points to ruamel.yaml for comment round-trip, so it does not preserve comments.
  - **ruamel.yaml remains the only maintained choice.** If the config format may change, tomlkit 0.15.1 (2026-07-17, MIT) preserves comments for TOML.

## 9. Console (topic 8)
- **prompt_toolkit 3.0.53 (2026-07-26)**, BSD-3-Clause, `>=3.10`, declares 3.14.
  - The official example `examples/prompts/asyncio-prompt.py` uses `with patch_stdout(): ... await PromptSession().prompt_async()`
    alongside other tasks.
  - `patch_stdout(raw: bool = False)` redirects both stdout **and stderr** into a proxy. Use `raw=True` to keep VT100 escapes (rich colours).
  - Its docstring warns to enter it after any `asyncio.set_event_loop()` change.
  - Sources: https://github.com/prompt-toolkit/python-prompt-toolkit/blob/main/src/prompt_toolkit/patch_stdout.py ,
    docs/pages/advanced_topics/asyncio.rst
- **rich 15.0.0 (2026-04-12)**, MIT, `>=3.9`. The only breaking change is dropping Python 3.8 (CHANGELOG).

## 10. Google Sheets (topic 9)
- **gspread 6.2.1 (2025-05-14)**, MIT, `>=3.8` (classifiers ≤3.11), depends on google-auth + google-auth-oauthlib.
  - README carries a "**Maintainer needed**" notice.
  - Commits continued to 2026-07-30 (backoff fixes, delete non-contiguous rows), but nothing has been released since 6.2.1.
- **gspread-asyncio 3.0.0 (2026-08-30)**, MIT, `>=3.11`, pins `gspread==6.2.*` and `requests==2.*`.
  - Breaking change: classes renamed to `ClientManager`, `Client`, `Spreadsheet`, `Worksheet`.
  - It runs every gspread call in a thread-pool executor with built-in rate limiting.
- **google-auth 2.61.0 (2026-10-07)**, Apache-2.0, `>=3.10`, declares 3.14/3.15. google-auth-oauthlib 1.5.0 (2026-09-29), Apache-2.0.

## 11. Web (topic 10)
- **FastAPI 0.142.4 (2026-10-07)**, MIT, `>=3.10`.
  - Core dependencies now include **`opentelemetry-api>=1.44.0`**.
  - Release notes on master: unreleased "Require opt-in for automatic OpenTelemetry exporter setup".
- **Starlette 1.7.0 (2026-09-23)**, BSD-3-Clause, `>=3.10`. It requires AnyIO 4 and adds experimental OpenTelemetry middleware.
  Its `full` extra lists both `httpx<0.29,>=0.27` and `httpx2>=2.0.0`.
- **Litestar 2.24.0 (2026-06-11)**, MIT, `>=3.8,<4`, declares 3.14. There is no 3.x on PyPI.
- **uvicorn 0.54.0 (2026-09-25)**, BSD-3-Clause, `>=3.10`. 0.52/0.53 added experimental `zttp` HTTP/1.1 and HTTP/2 backends.
- **Embedding in an existing loop** (official docs, https://github.com/Kludex/uvicorn/blob/main/docs/index.md, section "Config and Server instances"):
  ```python
  config = uvicorn.Config(app, host="127.0.0.1", port=8080, log_level="info")
  server = uvicorn.Server(config)
  await server.serve()          # e.g. as an asyncio.Task next to bot.start()
  ```
  - Caveat from `uvicorn/server.py@0.54.0`: `serve()` wraps `_serve()` in `capture_signals()`. On the main thread this
    installs `signal.signal` handlers for SIGINT/SIGTERM (and SIGBREAK) for the server's lifetime.
  - After shutdown it restores the previous handlers and re-raises the captured signals.
  - To stop it programmatically, set `server.should_exit = True`. Plan one shutdown owner across discord.py, prompt_toolkit and uvicorn.

## 12. HTTP / HTML (topic 11)
- **aiohttp 3.14.4 (2026-10-05)**, `Apache-2.0 AND MIT`, `>=3.10`, cp314 ×23 + cp314t ×18. discord.py 2.7.1 requires
  `aiohttp>=3.7.4,<4`, and 3.14.4 satisfies it. 2.7.1 fixed an aiohttp websocket-timeout deprecation warning.
- **httpx 0.28.1 (2024-12-06)** is still the latest stable, BSD-3-Clause; only `1.0.devN` pre-releases since (1.0.dev6, 2026-08-31).
  Pydantic forked it as **httpx2 2.13.1 (2026-09-23)**, BSD-3-Clause, `>=3.10`, import name `httpx2`.
  Its README: "With HTTPX itself seeing limited activity recently, Pydantic is picking up stewardship under the HTTPX2 name."
- **beautifulsoup4 4.15.0 (2026-06-07)**, MIT, `>=3.7`, pure.
- **selectolax 1.0.0 (2026-10-03)**, MIT, `<3.16,>=3.9`, cp314 + cp314t wheels.
  - **Breaking change: the Modest backend was removed**; only Lexbor remains (`from selectolax.lexbor import LexborHTMLParser`).
  - `parse_fragment()` was removed.
  - With Modest gone, the LGPL-2.1 component is also gone.
- lxml 6.1.3 (2026-09-02), BSD-3-Clause, cp314 + cp314t wheels; 7.0.0b1 is in beta.

## 13. i18n (topic 12)
- discord.py Translator, from source at v2.7.1 (`discord/app_commands/translator.py`) and docs
  (https://discordpy.readthedocs.io/en/latest/interactions/api.html#translator):
  ```python
  class Translator:
      async def load(self) -> None: ...      # called by CommandTree.set_translator
      async def unload(self) -> None: ...    # on replace / Client.close
      async def translate(self, string: locale_str, locale: discord.Locale,
                          context: TranslationContextTypes) -> Optional[str]: ...
  class locale_str:
      def __init__(self, message: str, /, **kwargs: Any): ...   # .message, .extras
  ```
  - `TranslationContextLocation` values: command_name, command_description, group_name, group_description,
    parameter_name, parameter_description, choice_name, other.
  - Install with `await tree.set_translator(MyTranslator())`. Translation runs during `await tree.sync()`.
  - `translate()` returns `None` when there is no translation.
  - Exceptions are wrapped in `TranslationError`.
  - `locale_str.message` must equal the default (English) name. Use `extras` (kwargs) to carry a message ID for Fluent/gettext-style catalogs.
  - The translator covers command metadata only. Runtime message text must be localized separately, e.g. by `interaction.locale`.
- **Babel 2.18.0 (2026-02-01)**, BSD-3-Clause, `>=3.8`, declares 3.14.

## 14. Licenses vs AGPL-3.0 (topic 13)

| Component | License (source) | AGPL-3.0 combination |
|---|---|---|
| discord.py | MIT (GitHub/PyPI) | OK |
| aiohttp | Apache-2.0 AND MIT (PyPI expr; GitHub Apache-2.0) | OK (Apache-2.0 is GPLv3/AGPLv3-compatible) |
| audioop-lts | PSF-2.0 | OK |
| PyNaCl | Apache-2.0 (bundles libsodium, ISC) | OK |
| davey | MIT (GitHub; PyPI classifier) | OK |
| orjson (discord.py `[speed]`) | MPL-2.0 AND (Apache-2.0 OR MIT) | OK (MPL-2.0 is GPL-compatible) |
| pymongo | Apache-2.0 | OK |
| pydantic / pydantic-core / pydantic-settings | MIT | OK |
| msgspec | BSD-3-Clause | OK |
| PyYAML | MIT | OK |
| ruamel.yaml | MIT | OK |
| prompt_toolkit | BSD-3-Clause | OK |
| rich | MIT | OK |
| yt-dlp (PyPI) | Unlicense; yt-dlp-ejs Unlicense AND MIT AND ISC; `[default]` pulls certifi (MPL-2.0) | OK. MPL-2.0 is GPL-compatible. Avoid redistributing the PyInstaller exe, which is GPLv3+ (still compatible) |
| deno | MIT | OK (separate process) |
| FFmpeg | LGPL-2.1+ or GPL depending on build | OK as a separate executable |
| wavelink / mafic / lavalink.py / SonoLink | MIT | OK |
| pomice | GPL-3.0 | OK. GPLv3 and AGPLv3 §13 explicitly allow combination; the pomice part stays GPLv3 |
| Lavalink server | MIT (separate JVM process) | OK |
| gspread / gspread-asyncio | MIT | OK |
| google-auth(-oauthlib) | Apache-2.0 | OK |
| FastAPI | MIT | OK |
| Starlette / uvicorn | BSD-3-Clause | OK |
| Litestar | MIT | OK |
| aiosqlite | MIT | OK |
| SQLAlchemy | MIT | OK |
| httpx / httpx2 | BSD-3-Clause | OK |
| bs4 / selectolax | MIT | OK |
| lxml / Babel | BSD-3-Clause | OK |
| testcontainers | Apache-2.0 (test-only) | OK |
| pytest-mongo | LGPL-3.0-or-later (test-only) | OK |
| mongomock | ISC | OK |
| **SecantusDB** | **GPL-2.0-only** AND CC-BY-4.0 | **Incompatible** with (A)GPLv3 if linked or distributed together. Only acceptable as an unshipped, out-of-process test server; otherwise avoid |

- No incompatibility in the main runtime stack. Main obligation: AGPL §13. The Ktor-replacement web dashboard must
  offer its Corresponding Source to network users.

## 15. Unconfirmed / flags
- discord.py does not declare 3.14 in classifiers (CI `3.x` plus 3.14-specific fixes imply support).
  wavelink (≤3.12), gspread (≤3.11), httpx 0.28.1 (≤3.12), mongomock (≤3.12), pomice (3.8) and aiosqlite
  (CI ≤3.13) do not declare 3.14 either. All are pure Python, so a smoke test on 3.14 is recommended.
- DAVE support of `discord-ext-songbird` is inferred from its Cargo.lock, not stated.
- Async support in mongomock-ng and SecantusDB's PyMongo-async validation are unverified.
- The non-DAVE behaviour of stage channels for bots is an inference from the blog's "stage channels are the one exception".
- The DAVE enforcement date differs by source: developer docs say March 1 2026; support articles and the status incident say March 2 2026 (actual).

## 16. Primary sources (accessed 2026-10-08)
- PyPI JSON API: https://pypi.org/pypi/{discord.py,davey,PyNaCl,audioop-lts,aiohttp,yt-dlp,yt-dlp-ejs,deno,wavelink,mafic,pomice,lavalink,sonolink,pymongo,motor,mongomock,mongomock-ng,mongomock-motor,testcontainers,pymongo-inmemory,pytest-mongo,SecantusDB,montydb,aiosqlite,SQLAlchemy,pydantic,pydantic-core,pydantic-settings,msgspec,PyYAML,ruamel.yaml,ruamel.yaml.clib,ruamel.yaml.clibz,strictyaml,ruyaml,yaml-rs,tomlkit,prompt_toolkit,rich,gspread,gspread-asyncio,google-auth,google-auth-oauthlib,fastapi,starlette,litestar,uvicorn,httpx,httpx2,beautifulsoup4,selectolax,lxml,Babel,greenlet,orjson,discord-ext-voice-recv,discord-ext-songbird,revvlink}/json
- discord.py v2.7.1: https://github.com/Rapptz/discord.py/tree/v2.7.1 (pyproject.toml, requirements.txt, discord/voice_state.py, voice_client.py, gateway.py, ui/, app_commands/translator.py); changelog https://github.com/Rapptz/discord.py/blob/master/docs/whats_new.rst
- Discord: https://docs.discord.com/developers/change-log (2024-09-17, 2025-09-02 entries); https://docs.discord.com/developers/topics/voice-connections ; https://docs.discord.com/developers/topics/opcodes-and-status-codes ; https://support.discord.com/hc/en-us/articles/38025123604631 ; https://support.discord.com/hc/en-us/articles/38749827197591 ; https://discordstatus.com/incidents/k22tny62jcw3 ; https://discord.com/blog/every-voice-and-video-call-on-discord-is-now-end-to-end-encrypted (2026-05-18)
- yt-dlp: https://github.com/yt-dlp/yt-dlp/releases/tag/2026.08.19 ; README @2026.08.19 ; wiki EJS / PO-Token-Guide / Extractors (snapshot 2026-09-27); issue #12482
- Lavalink: https://github.com/lavalink-devs/Lavalink/releases (4.2.0 2026-02-28, 4.2.2 2026-03-06); docs/clients.md; youtube-source releases
- Client releases: github.com/PythonistaGuild/Wavelink/releases, github.com/ooliver1/mafic/releases, github.com/cloudwithax/pomice/releases, github.com/Devoxin/Lavalink.py/releases, github.com/sonolink/sonolink/releases
- JDA/JDAVE/lavaplayer: github.com/discord-jda/JDA (README; release v6.7.0), github.com/MinnDevelopment/jdave (README), repo1.maven.org metadata for club.minnced:jdave-api and dev.arbjerg:lavaplayer
- MongoDB: https://github.com/mongodb/mongo-python-driver/blob/master/doc/changelog.rst ; https://github.com/mongodb/motor (README) ; https://motor.readthedocs.io/en/stable/ ; github.com/mongomock/mongomock ; github.com/michaelkryukov/mongomock_motor ; testcontainers-python tag testcontainers-v4.15.0 ; github.com/kaizendorks/pymongo_inmemory
- uvicorn docs/index.md + uvicorn/server.py @0.54.0 ; prompt_toolkit patch_stdout.py + examples/prompts/asyncio-prompt.py ; rich CHANGELOG ; gspread README ; gspread_asyncio release 3.0.0 ; httpx2 README ; selectolax CHANGES.md ; aiosqlite CHANGELOG + ci.yml ; ruamel.yaml PyPI description
