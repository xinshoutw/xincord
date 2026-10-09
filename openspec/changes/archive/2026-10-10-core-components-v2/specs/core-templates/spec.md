## ADDED Requirements

### Requirement: Components V2 templates are validated when they load
`components_v2` entries SHALL be validated when the template loads: each needs a known `type`
(case and `-` ignored; `string_select_menu` and `entity_select_menu` as aliases) and that type's
required fields. With `is_components_v2`, `content` and `embeds` SHALL be empty and at least one
component present; without it, `components_v2` SHALL hold only action rows.

#### Scenario: Valid V2 template loads
- **WHEN** v3's full Components V2 example is loaded
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

### Requirement: V2 interactive components follow v3
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
