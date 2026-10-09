# core-templates Specification

## Purpose
Turns a plugin's YAML message and modal templates into discord.py content, embeds, views and
modals, with placeholders, runtime models and plugin-built component IDs.

## Requirements

### Requirement: Templates are validated when they load
Loading a template SHALL parse its YAML, including the `!ButtonsComponent`, `!StringSelectMenu`
and `!EntitySelectMenu` tags, and validate it. Broken YAML or invalid values SHALL fail with an
error naming the file; unknown keys SHALL be logged as warnings. Loading a plugin's templates SHALL
load every message and modal template of every locale.

#### Scenario: Valid template loads
- **WHEN** a template with content, an embed and a buttons row is loaded
- **THEN** it loads without warnings

#### Scenario: Invalid template fails
- **WHEN** a template has an unknown tag, a button style of 9, or a timestamp that is neither
  `%now%` nor digits
- **THEN** loading fails naming the file

#### Scenario: Unknown key warns
- **WHEN** an embed has the key `colour_code`
- **THEN** loading succeeds and a warning names the file and the key

### Requirement: Message text is rendered with placeholders
Rendering SHALL apply the given placeholder values to the content and to every text of embeds and
components, including the `uid` values given to the ID builder.

#### Scenario: Content and embed text
- **WHEN** content, title, description, field name and value, footer, and button label use
  `%user_name%`
- **THEN** every rendered text contains the value

### Requirement: URL fields need an http result
The author URL and icon, title URL, thumbnail, image and footer icon SHALL be set only when their
rendered value starts with `http`.

#### Scenario: Placeholder without icon
- **WHEN** the author icon renders to `-` and the thumbnail to `https://example.com/a.png`
- **THEN** the embed has no author icon and has that thumbnail

### Requirement: Empty embeds are dropped
An embed with no title, description, timestamp, thumbnail, author, footer, image or fields after
rendering SHALL be left out of the message.

#### Scenario: Only a color
- **WHEN** an embed has only `color_code`
- **THEN** the message has no embeds

### Requirement: Colors and timestamps follow v3
`color_code` SHALL accept `#RRGGBB` and `0xRRGGBB`, rendered first when it uses placeholders.
`timestamp` SHALL accept `%now%` (the render time) or epoch milliseconds.

#### Scenario: Color and epoch timestamp
- **WHEN** an embed has `color_code: "0x9bd9d5"` and `timestamp: "1723675788491"`
- **THEN** the color is 0x9bd9d5 and the timestamp is 2024-08-14T22:49:48.491Z

### Requirement: Components keep their rows
Each entry of `components` SHALL become one row of a view: buttons (styles 1 to 5, link buttons
with `url`, the others with an ID built from `uid`), a string select with options, or an entity
select for users, roles or channels (with channel types). The view SHALL be stopped so discord.py
does not dispatch its interactions.

#### Scenario: Two rows
- **WHEN** a template has a buttons row with a link and a primary button, then a channel select
- **THEN** the view has the buttons in row 0 and the channel select in row 1, and is stopped

#### Scenario: Components need an ID builder
- **WHEN** a template with a non-link component is rendered without an ID builder
- **THEN** rendering fails

### Requirement: Model keys insert runtime objects
A `model_key` on the message, an embed, a field, a row, a button, a button emoji or an option SHALL
be replaced by the object the caller supplies under that key. A missing key or an object of the
wrong kind SHALL fail with an error naming the key.

#### Scenario: Field and button models
- **WHEN** a field and a button use `model_key` and the caller supplies a field and a button
- **THEN** the rendered embed and view contain them in place

#### Scenario: Missing model
- **WHEN** a template uses `model_key: board` and no model named `board` is supplied
- **THEN** rendering fails naming `board`

### Requirement: Modal templates render text inputs
A modal template SHALL render to a modal whose ID is built from `uid` and whose title and text
inputs are rendered with placeholders. Text inputs SHALL use `SHORT` or `PARAGRAPH`, set the value
and placeholder only when they render non-blank, and set lengths only when they are zero or more.
The modal SHALL be stopped.

#### Scenario: Modal with two inputs
- **WHEN** a modal template has a required SHORT input with `max_length: 20` and an optional
  PARAGRAPH input whose value renders blank
- **THEN** the modal has both inputs, the first limited to 20 characters, the second without a
  default value
