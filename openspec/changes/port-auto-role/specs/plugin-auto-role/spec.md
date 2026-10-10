# Spec Delta

## Purpose

Members who join a configured guild get that guild's configured roles.

## ADDED Requirements

### Requirement: The plugin installs as AutoRole
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `AutoRole`, pointing to `xincord.plugins.auto_role`, with no dependencies and the members
intent, which the bot then requests. It SHALL bundle a default `config.yaml`, which its first load
writes to `plugins/AutoRole/`, and no lang files.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `AutoRole` enabled
- **THEN** it returns `AutoRole` from `xincord.plugins.auto_role` with no dependencies and the
  members intent

#### Scenario: The bot requests the members intent
- **WHEN** a bot is created for the enabled `AutoRole`
- **THEN** its intents include the members intent

#### Scenario: First load creates the config
- **WHEN** the plugin loads in an empty directory
- **THEN** `plugins/AutoRole/config.yaml` holds the bundled default and no `lang` directory is
  written

### Requirement: The config lists guilds and their roles
`config.yaml` SHALL have a required `guilds` list whose entries have a positive `guild_id` and a
non-empty `role_ids` list of integers, as in v3; the bundled default SHALL list no guilds. A v3
config file SHALL load unchanged, with a warning that names its `enabled` key. A guild listed twice
SHALL use its last entry, as in v3. An invalid file SHALL disable only this plugin, with an error
that names the key.

#### Scenario: v3 config file
- **WHEN** `config.yaml` is v3's, with `enabled: true` and one guild with two 18-digit role IDs
- **THEN** the plugin loads with that guild and its roles, and logs a warning that names `enabled`

#### Scenario: Default config
- **WHEN** the plugin loads with the bundled `config.yaml`
- **THEN** it gives roles in no guild

#### Scenario: Invalid entries
- **WHEN** `guilds` is missing, a `guild_id` is 0, or a `role_ids` list is empty
- **THEN** the plugin does not load, and the error names `guilds`, `guilds.0.guild_id` or
  `guilds.0.role_ids`

#### Scenario: Guild listed twice
- **WHEN** two entries have the same `guild_id`
- **THEN** that guild's roles are the last entry's

### Requirement: Members who join get the guild's roles
When a member, bot or not, joins a guild that the config lists, the plugin SHALL add each of that
guild's configured roles with its own request, so that the member keeps every other role, looking
the roles up in that guild at the join. A role listed twice SHALL be requested once. Members who
join other guilds SHALL be left alone.

#### Scenario: Join in a configured guild
- **WHEN** a member joins guild 10, configured with roles 11 and 12, which the bot can give
- **THEN** roles 11 and 12 are added with one add-role request each

#### Scenario: Bot joins
- **WHEN** a bot joins guild 10
- **THEN** it gets roles 11 and 12 too

#### Scenario: Role listed twice
- **WHEN** guild 10's entry lists role 11 twice
- **THEN** role 11 is requested once

#### Scenario: Join in another guild
- **WHEN** a member joins a guild that the config does not list
- **THEN** no role is requested

### Requirement: Roles that cannot be given are skipped
The plugin SHALL skip, with a warning that names the role and the guild, a configured role that is
missing from the joined guild, such as another guild's role, or that the bot cannot give (managed,
`@everyone`, or not below the bot's highest role), and still add the others. Without Manage Roles
it SHALL request nothing and log a warning that names the guild. A failed request SHALL be logged,
and the remaining roles still requested.

#### Scenario: Missing role
- **WHEN** a member joins guild 10 while role 12 is not in it
- **THEN** role 11 is added and a warning names role 12 and guild 10

#### Scenario: Role created later
- **WHEN** role 12 is created in guild 10 after a member joined without it, and another member
  joins
- **THEN** the second member gets roles 11 and 12, without a reload

#### Scenario: Role the bot cannot give
- **WHEN** a member joins guild 10 and the bot cannot give role 11
- **THEN** role 12 is added and a warning names role 11 and guild 10

#### Scenario: Missing Manage Roles
- **WHEN** a member joins guild 10 and the bot lacks Manage Roles there
- **THEN** no role is requested and a warning names guild 10

#### Scenario: Failed request
- **WHEN** the request for role 11 fails
- **THEN** a warning names role 11 and the member, and role 12 is still requested

### Requirement: Problems are logged when the bot is ready
When the bot becomes ready, or when the plugin loads into a ready bot, the plugin SHALL log a
warning for each configured guild that the bot is not in, each configured guild where it lacks
Manage Roles, and each configured role that it cannot give there. Nothing SHALL be checked before
the bot is ready.

#### Scenario: Ready
- **WHEN** the plugin loaded before the bot was ready, and the bot becomes ready with a configured
  guild it is not in, a guild without Manage Roles, a missing role and a role it cannot give
- **THEN** nothing was logged at the load, a warning names each problem, and no warning names a
  role that the bot can give

#### Scenario: Loaded into a ready bot
- **WHEN** the plugin loads while the bot is ready, as after `/xincord reload AutoRole`
- **THEN** the warnings are logged during the load
