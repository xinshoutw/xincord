# Spec Delta

## ADDED Requirements

### Requirement: Status rotation
Once the bot is ready it SHALL show the configured activities in order, each for its `seconds`,
and start again after the last. A single activity SHALL be set once; no activities SHALL leave the
presence alone. Playing, listening, watching and competing SHALL use the text as the name,
streaming SHALL add its URL, and custom SHALL set a custom status. A failed update SHALL be logged
and the rotation SHALL go on. A full reload SHALL restart the rotation with the new list.

#### Scenario: Activity kinds
- **WHEN** each activity type is converted
- **THEN** it becomes the matching discord.py activity with the text, and the URL for streaming

#### Scenario: Rotation
- **WHEN** the bot is ready with two activities, with one, and with none
- **THEN** the first two alternate, the single one is set once, and the presence is not changed

#### Scenario: Failures and reload
- **WHEN** a presence update fails, and later a full reload changes the activities
- **THEN** the failure is logged and the next activity follows, and after the reload the new
  activities are shown

### Requirement: Interaction console lines
The bot SHALL log `[KIND] <user name>: <text>` for each slash command (`CMD`, with JDA's command
string), message command (`MSG`, its name), button (`BTN`), string select (`STRING`), entity
select (`ENTITY`) and modal (`MODAL`); the text of components and modals SHALL be the custom ID.
Autocomplete and user commands SHALL NOT be logged.

#### Scenario: Console lines
- **WHEN** a slash command, a message command, a button, a string select, a user select, a modal,
  an autocomplete and a user command arrive from alice
- **THEN** the log has `[CMD] alice: /ping count: 2`, `[MSG] alice: Report`, `[BTN] alice: b`,
  `[STRING] alice: s`, `[ENTITY] alice: u` and `[MODAL] alice: m`, and nothing for the others

### Requirement: Interaction log channels
For each `interaction_log` target whose `types` include the interaction's type (`command`: slash
commands, `button`: buttons, `modal`: modals), the bot SHALL send the target's `format`, rendered
with v3's user keys, the interaction keys, `cl_type` (`CMD`, `BTN` or `MODAL`) and
`cl_interaction_string`, to the target channel. These messages SHALL NOT ping. A failed send SHALL
be logged without affecting the others; a full reload SHALL apply new targets.

#### Scenario: Matching targets
- **WHEN** one target lists `command` and `modal`, another `button`, and alice uses `/ping`, a
  button `b` and a modal `m`
- **THEN** the first channel gets ``[CMD] alice `/ping` `` and ``[MODAL] alice `m` ``, and the
  second gets ``[BTN] alice `b` ``

#### Scenario: No pings, failures and reload
- **WHEN** a format contains `%user_mention%`, one channel rejects the message, and a reload adds a
  target
- **THEN** no message allows mentions, the rejection is logged while the other channel still gets
  its line, and the next interaction also reaches the added target
