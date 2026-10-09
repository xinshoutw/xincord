# core-component-routing Specification

## Purpose
Delivers each button, select and modal submission to the plugin that owns its ID, and upgrades the
v3 IDs on a message the first time one of them is used.

## Requirements

### Requirement: Component and modal interactions reach their plugin
A plugin SHALL register a component ID codec and a handler from its setup. The bot SHALL send each
component and modal-submit interaction whose custom ID a registered codec owns, in either format,
to that handler with the parsed fields. Interactions that no codec owns SHALL be ignored. An
exception from parsing or from a handler SHALL be logged with the plugin's name.

#### Scenario: Routed interactions
- **WHEN** Ticket registered its codec and a button with `ticket:1:a=press` and a modal with
  `ticket@a:submit;f:1` are used
- **THEN** Ticket's handler receives them with `{action: press}` and with
  `{action: submit, btn_index: 1}` marked legacy

#### Scenario: Unowned and failing interactions
- **WHEN** an interaction's ID belongs to no codec, and another reaches a handler that raises
- **THEN** no handler runs for the first, and the error of the second is logged with the plugin's
  name

### Requirement: Routes follow the plugin's lifecycle
Routes SHALL belong to the plugin that registered them. They SHALL be removed when that plugin
fails to load and before it is reloaded, so only the loaded version's handlers run.

#### Scenario: Reload replaces the handler
- **WHEN** a plugin that registered a route is reloaded and its button is used
- **THEN** only the reloaded version's handler runs, once

#### Scenario: Failed load leaves no route
- **WHEN** a plugin registers a route and then fails in its setup
- **THEN** its button reaches no handler

### Requirement: Legacy IDs are upgraded after use
After a handler ran for a legacy ID on a message that is not ephemeral, the bot SHALL fetch the
message's current state, rewrite its legacy IDs with the registered codecs and edit it once if
anything changed. Messages without legacy IDs SHALL NOT be edited, and failures SHALL be logged.

#### Scenario: Panel is upgraded
- **WHEN** a legacy button on a panel, or on a Components V2 message, is used
- **THEN** the message is edited once with new-format IDs and its other items unchanged

#### Scenario: Nothing to upgrade
- **WHEN** the handler already replaced the IDs, the message is ephemeral, or fetching it fails
- **THEN** the message is not edited, and a failed fetch is logged
