## Decisions

### An exact pin

The two distributions come from one tag with one version, which `release_version.py` checks
already, and the plugins are tested with that core only. `==` says so; a range such as `>=1.0,<2`
would let pip pair a plugins release with a core it was never tested with. uv's workspace source
still resolves the requirement to the workspace member, whose version matches. Renovate leaves
the workspace's packages alone, so it never moves the pin.

### The check

`release_version` reads the plugins' `project.dependencies`, finds the requirement on `xincord`
and fails unless it is `xincord==<version>`, as it fails when the versions differ. A release then
cannot ship a pin left at the previous version.

### The plugin API

A document, no code. The names are the ones the bundled plugins import, which a plugin of the
owner's or anyone else's would use too: the context, the store, the config model, the lang, the
component IDs, the templates and the placeholders, and the `Bot` methods that plugins call. From
1.0.0 a release that removes one of them or changes it incompatibly is a major release; any other
name of `xincord.core` may change in any release.
