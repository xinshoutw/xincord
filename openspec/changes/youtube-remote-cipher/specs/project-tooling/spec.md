## MODIFIED Requirements

### Requirement: Renovate updates the versions that no manager reads
`.github/renovate.json` SHALL update the OpenSpec CLI's version from npm in every file of the gate,
the workflows and the docs that pins it, all of which SHALL pin the same version. It SHALL update
the Lavalink plugins of `lavalink/application.yml` from Maven at
`https://maven.lavalink.dev/releases`, the repository that the node downloads them from, and leave
a plugin pinned to a snapshot's commit alone.

#### Scenario: OpenSpec CLI
- **WHEN** the repository's files, except archived changes and research notes, are searched for a
  pinned OpenSpec CLI
- **THEN** each pin is in a file that the npm regex manager reads, its pattern matches every pin,
  and all pins name the same version

#### Scenario: Lavalink plugins
- **WHEN** the Maven regex manager's pattern is applied to `lavalink/application.yml`
- **THEN** it finds youtube-source and LavaSrc with their exact releases or snapshot commits,
  looked up at `https://maven.lavalink.dev/releases`, and a rule disables updates of a version that
  is a 40-character commit
