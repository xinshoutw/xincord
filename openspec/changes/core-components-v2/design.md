## Context

v3 keeps `components_v2` as raw JSON (`MessageCreator.kt:92-127`) and builds JDA components from it
at render time (`v2/builder/MessageBuilder.kt`): types are normalized (`lowercase`, `-` to `_`),
every component may carry `model_key` and an integer `id`, section accessories are inferred,
media can be a URL, a local `file_path` (uploaded) or an attachment `file_name`, buttons accept
style numbers and names, and a top-level embed model is converted into a container
(`MessageBuilder.kt:414-471`). With `is_components_v2`, content and embeds must be empty and at
least one component is required; without it, `components_v2` may only hold action rows.

## Goals / Non-Goals

**Goals:** v3's V2 schema and output with discord.py's V2 items, validated at load.

**Non-Goals:** new component types beyond v3's, V2 modal components.

## Decisions

- **Schema.** pydantic models per component type behind a callable discriminator that normalizes
  `type` and maps the select aliases, so v3 files load unchanged. Required fields are checked unless
  `model_key` is set, as for v1.
- **Output.** V2 mode renders a `discord.ui.LayoutView(timeout=None)`, stopped like v1 views. v1
  rows in a V2 message become `discord.ui.ActionRow`s. A non-V2 template whose `components_v2`
  holds action rows renders them as rows of a regular view, which is what v3 sent.
- **Media.** `url` is rendered; `file_name` becomes `attachment://<name>`; `file_path` creates a
  `discord.File` that the `Message` carries in `files`, referenced as `attachment://<name>`.
- **Disabled containers and sections.** discord.py has no container-level `disabled`; the renderer
  disables every button and select inside instead, which is what JDA's `withDisabled` does.
- **Embed models** become a container: author and title as `###`/`##` headings (linked when they
  have URLs), the description, one text per field (`**name**` and value), the image as a gallery,
  and the footer and timestamp in italics after a separator; the thumbnail (or author icon) makes
  the header a section. The accent color is the embed color.

### v3 behaved differently

- v3 behaved differently: V2 components were checked only when a message was rendered; they are now
  validated when the plugin loads.
- v3 behaved differently: without `is_components_v2`, a top-level `model_key` in `components_v2`
  could supply a whole action row; xincord accepts only action rows there (models still work inside
  them), because discord.py cannot move a prebuilt row into a regular view.
- v3 behaved differently: an embed model's timestamp became ISO text in the footer line; xincord
  writes Discord's `<t:...:f>` markup, which shows the reader's local time as the embed did.

## Risks / Trade-offs

- No shipped template exercises this code; tests cover v3's full example instead.

## User-visible changes

None.
