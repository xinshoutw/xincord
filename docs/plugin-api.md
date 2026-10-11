# Plugin API

What a plugin may use, the bundled ones and those of other distributions alike. From 1.0.0 these
names follow semantic versioning: a release that removes one or changes it incompatibly is a major
release. Every other name in `xincord.core` is internal and may change in any release.

## A plugin

- An entry point in the group `xincord.plugins`, named after the plugin (letters, digits, `_` and
  `-`), which the core config's `plugins` list names. Its module is a discord.py extension:
  `async def setup(bot)` gets the plugin's context with `bot.plugin_context(__name__)`.
- Optional module constants: `DEPENDS` and `SOFT_DEPENDS`, tuples of plugin names loaded first,
  and `INTENTS`, the `discord.Intents` the plugin needs.
- Files bundled beside the module: `config.yaml`, copied to `plugins/<Name>/` on the first start,
  and `lang/`, exported there file by file when missing.

`xincord.plugins.example` is the template.

## The core's names

| Module | Names |
|---|---|
| `xincord.core.bot` | `Bot`: `plugin_context`, `route`, `relay_gateway_event` |
| `xincord.core.plugins` | `PluginContext`: `info`, `directory`, `store`, `data_directory`, `config`, `lang` |
| `xincord.core.config` | `Model`, `ConfigError` |
| `xincord.core.storage` | `Store` and its public methods, `JSON` |
| `xincord.core.i18n` | `Lang` and its public methods |
| `xincord.core.component_ids` | `ComponentIds`, `ParsedId` |
| `xincord.core.templates` | `Templates`, `Message`, `MessageTemplate`, `IdBuilder`, `TemplateError`, `render_message`, `render_modal`, `modal_values` |
| `xincord.core.placeholders` | `render`, `placeholder_values`, `global_values`, `actor_values`, `guild_values`, `channel_values`, `event_values`, `UserLike`, `MemberLike`, `GuildLike` |

A plugin keeps its own tables in the store's database, named `<plugin>_<table>`, through
`Store.run`, and its own files in `PluginContext.data_directory`.

## Versions

`xincord-plugins` requires the `xincord` of its own release: both come from one tag. A plugin of
another distribution requires a range of the core's major version, such as `xincord>=1.0,<2`.
