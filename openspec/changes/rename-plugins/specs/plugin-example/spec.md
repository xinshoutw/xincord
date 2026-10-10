## RENAMED Requirements

- FROM: `### Requirement: The plugin installs as _Example`
- TO: `### Requirement: The plugin installs as Example`

## MODIFIED Requirements

### Requirement: The plugin installs as Example
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `Example`, pointing to `xincord.plugins.example`, with no dependencies and no extra
intents. It SHALL bundle a default `config.yaml` and en-US and zh-TW lang files, which its first
load writes to `plugins/Example/`.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `Example` enabled
- **THEN** it returns `Example` from `xincord.plugins.example` with no dependencies and no intents

#### Scenario: First load creates the files
- **WHEN** the plugin loads in an empty directory
- **THEN** `plugins/Example/config.yaml` holds the bundled default and the en-US and zh-TW lang
  files exist
