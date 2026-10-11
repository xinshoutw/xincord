## Decisions

### The image job

A second job beside `gate`, so that a failed build is a check of its own. linux/amd64 only: the
runner's own architecture, no QEMU; the release builds arm64 as well. `load: true` puts the image
in the runner's Docker, and the GitHub Actions cache (`type=gha`) keeps the layers between runs.

Two checks in the image: `python -c` loads each `xincord.plugins` entry point, so every library a
plugin imports is in the slim image; and `xincord --no-online` starts the program with its default
config (the core and no plugin), as the entry point does. The plugins' own settings (an API key, a
node) are no CI's to give, so their loading stays with the gate's tests.

### Renovate's commit type

`config:recommended` includes `:semanticPrefixFixDepsChoreOthers`, whose package rules give every
package `chore` (`fix` for some dependency types). Package rules override the top-level options,
so the top-level `semanticCommitType: build` reached lock-file maintenance only. A first rule of
the repository's own, `matchPackageNames: ["*"]` with `build`, applies after the presets' rules
and before the GitHub Actions rule, which keeps `ci`. Renovate's validator 44.151.0 accepts it.
