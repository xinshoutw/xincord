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

### Requirement: Colors and timestamps are parsed
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

### Requirement: Components V2 templates are validated when they load
`components_v2` entries SHALL be validated when the template loads: each needs a known `type`
(case and `-` ignored; `string_select_menu` and `entity_select_menu` as aliases) and that type's
required fields. With `is_components_v2`, `content` and `embeds` SHALL be empty and at least one
component present; without it, `components_v2` SHALL hold only action rows.

#### Scenario: Valid V2 template loads
- **WHEN** the full Components V2 example is loaded
- **THEN** it loads without warnings

#### Scenario: V2 mode rules
- **WHEN** a V2 template has content, or a non-V2 template has a section in `components_v2`, or an
  entry has type `carousel`
- **THEN** loading fails naming the file

### Requirement: V2 messages render into a layout view
With `is_components_v2`, rendering SHALL produce a stopped layout view holding the components in
order: text displays, sections, thumbnails, media galleries, separators, files, containers and
action rows, with placeholders applied to their texts and URLs and each `id` kept. v1 rows SHALL
become action rows when `components_v2` is empty; a non-empty `components_v2` replaces them.

#### Scenario: Section, gallery and container
- **WHEN** a V2 template has a section with a thumbnail URL, a media gallery and a container with a
  separator and text
- **THEN** the layout view has those items in order with the given ids and rendered texts

#### Scenario: Local file
- **WHEN** a file display uses `file_path`
- **THEN** the message carries that file and the component references it as an attachment

### Requirement: Section accessories are inferred
A section accessory without `type` SHALL be a thumbnail when it has `url`, `file_path` or
`file_name`, and a button otherwise.

#### Scenario: Untyped accessories
- **WHEN** one section's accessory has only `url` and another's only `uid` and `label`
- **THEN** the first is a thumbnail and the second a button

### Requirement: V2 interactive components take styles and IDs
V2 buttons SHALL accept style numbers 1 to 6 or names (PRIMARY or BLUE, SECONDARY, GRAY or GREY,
SUCCESS or GREEN, DANGER or RED, LINK, PREMIUM); premium buttons need `sku` or `sku_id`; other
non-link components take `custom_id` (rendered) or `uid` (through the ID builder). Selects SHALL
apply `disabled` and default values.

#### Scenario: Styles and IDs
- **WHEN** an action row has a GREEN button with `uid`, a premium button with `sku_id` and a string
  select with `custom_id` and a default value
- **THEN** the button is a success button with the built ID, the premium button carries the SKU,
  and the select uses the rendered custom ID with that option selected

### Requirement: V2 model keys insert runtime objects
A `model_key` on any V2 component SHALL be replaced by the supplied discord.py item. An embed
supplied for a top-level model SHALL become a container holding its author and title as headings,
its description, fields, image and footer.

#### Scenario: Embed model as a container
- **WHEN** a top-level V2 component uses `model_key` and the caller supplies an embed with a title,
  a field and a color
- **THEN** the layout view holds a container with that accent color and texts for the title and
  the field

### Requirement: Embed fields are trimmed and never empty
Rendering SHALL remove the leading and trailing characters up to U+0020 from each embed field's name
and value, and SHALL give a name or value that is empty afterwards the text U+200E, because Discord refuses empty fields. Fields that a
`model_key` supplies SHALL get the same treatment.

#### Scenario: Empty value
- **WHEN** a field's value renders empty
- **THEN** the field's value is U+200E

#### Scenario: Padded text
- **WHEN** a field's name renders as ` name ` and its value as `value` followed by two newlines
- **THEN** the field's name is `name` and its value is `value`

### Requirement: Modal submissions are read back
`modal_values(data)` SHALL return the value of each text input in a modal submission's data by its
custom ID, whether the input sits in a label, as rendered modals send it, or in an action row.
Other components SHALL be ignored.

#### Scenario: Label and action row inputs
- **WHEN** a submission holds the input `form` in a label, the input `title` in an action row and a
  text display
- **THEN** the values of `form` and `title` are returned by their IDs
