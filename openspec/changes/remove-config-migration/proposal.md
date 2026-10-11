## Why

`python -m xincord.core.migrate_v3` converted the directory of an installation of the previous bot
into xincord's: the core config, the enabled plugins and the renamed plugins' directories. The
owner's two installations moved on 2026-10-12 and nothing else uses it; the owner asked for the
project to keep nothing of the previous bot.

## What Changes

- **Removed**: `xincord.core.migrate_v3` and its four requirements in `core-config`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `core-config`: the migration's requirements go.

## Impact

`src/xincord/core/migrate_v3.py` and `tests/core/test_migrate_v3.py` are deleted; the docs no
longer mention them. Nothing else imports the module.
