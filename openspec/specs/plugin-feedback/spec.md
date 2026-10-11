# plugin-feedback Specification

## Purpose
Administrators ask a member to rate the service with five star buttons; the member's stars and
feedback are posted to a submit channel.

## Requirements

### Requirement: The plugin installs as Feedback
The `xincord-plugins` distribution SHALL register the plugin in the `xincord.plugins` entry-point
group as `Feedback`, pointing to `xincord.plugins.feedback`, with no dependencies and no
intents. It SHALL bundle `config.yaml` and en-US and zh-TW lang files (`register.yaml`, the
`ask-message` and `print-result` messages and the `fill-form` modal), which its first load writes
to `plugins/Feedback/`.

#### Scenario: Discovered by name
- **WHEN** discovery runs with `Feedback` enabled
- **THEN** it returns `Feedback` from `xincord.plugins.feedback` with no dependencies and no
  intents

#### Scenario: First load creates the files
- **WHEN** the plugin loads in an empty directory
- **THEN** `plugins/Feedback/config.yaml` is the bundled file and the eight lang files exist
  under `plugins/Feedback/lang/`

### Requirement: The config holds the replies
`config.yaml` SHALL hold the required replies `form_no_permission`, `form_not_you` and
`form_success`, and `form_failure` and `form_submit_failure`, which default to English texts so
that a file with the three required replies loads and an `enabled` key only warns. Each reply SHALL be shown as
written and SHALL hold a non-blank text of at most 2000 characters; otherwise the plugin SHALL not
load, and the error SHALL name the key.

#### Scenario: A file with three replies
- **WHEN** `config.yaml` holds an `enabled` key and the three required replies
- **THEN** the plugin loads with those replies and the English defaults of the two others, and
  a warning names `enabled`

#### Scenario: Bundled file
- **WHEN** the bundled `config.yaml` loads
- **THEN** the five replies are zh-TW texts

#### Scenario: Invalid reply
- **WHEN** a required reply is missing, or a reply is blank or longer than 2000 characters
- **THEN** the plugin does not load and the error names the key

### Requirement: The command is a localized guild command
The plugin SHALL register `feedback` as a guild command that every member sees, with its
description and localizations, and two required
options: `member`, a user, and `submit-channel`, which offers text channels only. The command tree
SHALL defer it ephemerally before its callback runs.

#### Scenario: Command payload
- **WHEN** the guild command payload is built
- **THEN** `feedback` has its description, its en-US and zh-TW localizations,
  no default member permissions, the user option `member` and the channel option `submit-channel` with the channel
  type 0

#### Scenario: Command callback
- **WHEN** the command runs
- **THEN** its callback, bound to the plugin's cog, answers in the response that the tree deferred
  ephemerally

### Requirement: Administrators post a feedback form
When an administrator runs `feedback`, the plugin SHALL post `ask-message` in the command's
channel, rendered in the administrator's locale with the member's placeholder values and
`%fb_submit_channel_id%`, then replace the deferred response with `form_success`. Each of the five
star buttons SHALL carry the member's ID, the submit channel's ID and its star count.

#### Scenario: Form posted
- **WHEN** an administrator with an en-US or a zh-TW client runs `feedback` for member 7 with
  submit channel 6
- **THEN** the channel gets the embed in that locale over five gray buttons labeled with one to
  five stars, whose IDs are `feedback:1:a=submit_star;b=7;d=6;c=<stars>`, and the response is
  `form_success`

### Requirement: Only administrators post forms
The plugin SHALL replace the deferred response with `form_no_permission` and post nothing when the
user does not have the Administrator permission.

#### Scenario: Member without Administrator
- **WHEN** a member without Administrator runs `feedback`
- **THEN** the response is `form_no_permission` and nothing is posted

### Requirement: A form that cannot be posted is reported
When the submit channel is not a text channel, the `member` option names a user who is not a member
of the guild, or the command's channel takes no messages or refuses the form, the plugin SHALL post
nothing more, replace the deferred response with `form_failure` and log a warning that says why.

#### Scenario: Not a member
- **WHEN** the `member` option names a user who is not in the guild
- **THEN** nothing is posted, the response is `form_failure` and a warning names the user

#### Scenario: Not a text channel
- **WHEN** the submit channel is an announcement channel
- **THEN** nothing is posted, the response is `form_failure` and a warning names the channel

#### Scenario: Channel refuses the form
- **WHEN** the command's channel refuses the message, or takes no messages
- **THEN** the response is `form_failure` and a warning names the channel

### Requirement: Only the rated member presses a star
A star press by a user other than the one in the button's ID SHALL get `form_not_you` as an
ephemeral reply, and nothing else SHALL happen.

#### Scenario: Someone else presses
- **WHEN** user 8 presses a star of member 7's form
- **THEN** user 8 gets `form_not_you` ephemerally, no modal opens and the message stays as it was

### Requirement: A star opens the feedback modal
When the rated member presses a star, the plugin SHALL open `fill-form` in the member's locale with
the interaction's placeholder values, `%fb_star_count%` and `%fb_submit_channel_id%`, then edit the
message so that the pressed button is blue (primary) and its other buttons with IDs are gray
(secondary). A refused edit SHALL be logged, and the modal SHALL stay open.

#### Scenario: Modal opens
- **WHEN** member 7 with an en-US or a zh-TW client presses the three-star button
- **THEN** the modal shows its title and its optional paragraph input `form` of at most 1024
  characters in that locale, and the modal's ID is `feedback:1:a=submit_form;c=3;d=6`

#### Scenario: Pressed star highlighted
- **WHEN** member 7 presses the three-star button after the five-star one
- **THEN** after the modal opened, the message is edited with the three-star button primary and
  the four others secondary

#### Scenario: Edit refused
- **WHEN** Discord refuses the edit of the message
- **THEN** the modal has opened and a warning names the message

### Requirement: A submitted feedback is posted
On a submitted modal, the plugin SHALL acknowledge it without a message (a deferred edit), post
`print-result` in the submit channel, rendered in the guild's locale with the placeholder values of
the submitter, `%fb_stars%` and `%fb_content%` (the feedback as typed), and then delete the form. A
form that cannot be deleted SHALL be logged.

#### Scenario: Feedback posted
- **WHEN** member 7 submits three stars and the feedback `great` in a guild whose locale is en-US
  or zh-TW
- **THEN** the submit channel gets the review embed in that locale with the member's name,
  `★ ★ ★ ☆ ☆ ` and `great`, and the form is deleted after the review is posted

#### Scenario: Empty feedback
- **WHEN** the member leaves the feedback empty
- **THEN** the review is posted with U+200E as its field's value

#### Scenario: Placeholders in the feedback
- **WHEN** the feedback is `%user_id%`
- **THEN** the review shows `%user_id%` as typed

#### Scenario: Form already gone
- **WHEN** deleting the form fails
- **THEN** the review has been posted and a warning names the form

### Requirement: A feedback that cannot be posted keeps the form
When the submit channel is not one of the guild's text channels any more, or refuses the review, the
plugin SHALL keep the form, send `form_submit_failure` to the member as an ephemeral follow-up and
log a warning that names the channel.

#### Scenario: Channel gone
- **WHEN** the submit channel was deleted, or is no text channel of the guild
- **THEN** the form stays, the member gets `form_submit_failure` and a warning names the channel

#### Scenario: Channel refuses the review
- **WHEN** the submit channel refuses the review
- **THEN** the form stays, the member gets `form_submit_failure` and a warning names the channel

### Requirement: Stars are written as text
`%fb_stars%` SHALL be `★ ` once per star followed by `☆ ` up to five. A star count
that is not a whole number from 0 to 5 SHALL fail the press or the submission, which the core logs,
before anything is sent.

#### Scenario: Star counts
- **WHEN** the star count is 0, 3 or 5
- **THEN** `%fb_stars%` is five empty stars, `★ ★ ★ ☆ ☆ ` or five full stars, each star followed
  by a space

#### Scenario: Invalid star count
- **WHEN** a button or modal ID carries the star count `6` or `x`
- **THEN** no modal opens and nothing is posted

### Requirement: Legacy forms keep working
The plugin SHALL route the IDs of `ComponentIds("feedback", ("action", "user_id", "star_count",
"submit_channel_id"), legacy_prefix="feedbacker@")`: button presses with the action `submit_star`
and modal submissions with `submit_form`, in the legacy format too, after which the core upgrades
the form's IDs. Other actions SHALL get no response.

#### Scenario: Legacy star button
- **WHEN** member 7 presses `feedbacker@a:submit_star;b:7;d:6;c:3` on a legacy form
- **THEN** the modal opens and the form's buttons get IDs such as
  `feedback:1:a=submit_star;b=7;d=6;c=3`

#### Scenario: Legacy modal
- **WHEN** a modal with the ID `feedbacker@a:submit_form;c:3;d:6` is submitted
- **THEN** the review is posted in channel 6

#### Scenario: Other action
- **WHEN** a button with the action `other` is pressed
- **THEN** nothing is sent
