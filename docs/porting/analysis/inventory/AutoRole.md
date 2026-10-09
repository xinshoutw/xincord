# AutoRole — porting inventory (branch `main`)

Repo root: `/Users/xinshou/IdeaProjects/XsDiscordBotKt`. Plugin sources: `Plugins/AutoRole/src/main/kotlin/autorole/` (abbreviated `ar/`). Core: `Core/src/main/kotlin/core/` (`core/`).

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/AutoRole` |
| Kotlin files / LOC | 3 files / 81 physical lines (66 non-blank): `AutoRole.kt` (25), `Event.kt` (32), `config/ConfigSerializer.kt` (24) |
| Build | `build.gradle.kts` = `plugins { id("xs-plugin") }`; `gradle.properties` `version.patch=0` → `3.4.0-SNAPSHOT` |
| Purpose | When a member joins one of the configured guilds, set that member's roles to a configured list of role IDs. |
| Entry object | `object Event : PluginEventConfigure<ConfigSerializer>(true, ConfigSerializer.serializer())` (`ar/Event.kt:7`) |
| Base class | `PluginEventConfigure<C>` (`core/plugin/PluginEvent.kt:53-74`) |
| Listener flag | `true` |
| Business object | `object AutoRole` (`ar/AutoRole.kt:8`) — public `object`, lazily initialized on first access |

`src/main/resources/info.yaml`: `author: ${author}` (→ `xinshoutw`), `name: ${name}` (→ `AutoRole`), `coreApi: ${coreApi}` (→ `3.4`), `version: ${version}` (→ `3.4.0-SNAPSHOT`), `main: "tw.xinshou.discord.plugin.autorole.Event"`. No `prefix`, `description`, `component_prefix` (Core derives `autorole@`, `core/base/PluginLoader.kt:277-285`), `require_intents`, `require_cache_flags`, `require_member_cache_policies`, `depend_plugins`, `soft_depend_plugins`, `depend_jars`.

## 2. Lifecycle

- `load()` (`ar/Event.kt:8-15`): `super.load()` (no `lang/` resource exists, so nothing exported; reads/exports `plugins/AutoRole/config.yaml` with strict kaml). If disabled: WARN `AutoRole is disabled.`. Does **not** touch the `AutoRole` object — its state is computed lazily on the first `GuildMemberJoinEvent` (or first `reload()` while enabled).
- `AutoRole` object init (`ar/AutoRole.kt:9-12`): `trackedGuildIds = config.guilds.map { guildId }.toSet()`; `addRoles = config.guilds.associate { guildId to roleIds.mapNotNull { jdaBot.getRoleById(it) } }` — role lookup is **global across all cached guilds** (`JDA.getRoleById`), unresolvable IDs silently dropped; duplicate `guild_id` entries: last one wins in `addRoles`.
- `reload()` (`ar/Event.kt:17-26`): `super.reload()` re-reads config; if enabled → `AutoRole.reload()` recomputes both maps (`ar/AutoRole.kt:14-19`); if disabled, stale maps are kept (unused because handler checks `enabled`). Only invoked by the Web Dashboard (`core/base/BotLoader.kt:133-138`); console `reload` restarts everything (fresh class loader ⇒ fresh object).
- `unload()`: default. Background jobs: none. In-memory state: `trackedGuildIds: Set<Long>`, `addRoles: Map<Long, List<Role>>` (JDA `Role` entity references captured at init/reload; roles created/fixed later are not picked up until reload).

## 3. Slash commands & context menus

None (`guildCommands()`/`globalCommands()` not overridden → `null`).

## 4. Components

None.

## 5. Events

| JDA event | Filter | Behavior |
|---|---|---|
| `GuildMemberJoinEvent` (`ar/Event.kt:28-31` → `ar/AutoRole.kt:21-25`) | `config.enabled`; `event.guild.idLong ∈ trackedGuildIds` | `event.guild.modifyMemberRoles(event.member, addRoles.getValue(guildId)).queue()` |

Semantics of `Guild.modifyMemberRoles(Member, Collection<Role>)` (JDA docs): **replaces the member's complete role set** with the given roles (one `PATCH /guilds/{g}/members/{u}` with `roles: [...]`), not additive. For a freshly joined member the cached role set is normally empty, so the effect is "add these roles"; roles granted concurrently by others between the join event and the PATCH would be removed. JDA performs client-side checks and throws synchronously (handler aborts, JDA logs the exception; **no role is assigned at all**):
- `InsufficientPermissionException` — bot lacks `MANAGE_ROLES`;
- `HierarchyException` — any configured role is ≥ the bot's highest role;
- `IllegalArgumentException` — any role belongs to another guild (possible because lookup is global), is managed (bot/integration/booster role), or is `@everyone`.
If the resolved list equals the member's current roles (e.g. empty list for a new member) JDA returns a completed no-op action. REST failures (e.g. role deleted since init) are logged by JDA's default failure handler (`queue()` without callbacks). No bot filter: bots that join also get the roles. Pending (membership-screening) members are not special-cased.

## 6. Configuration

`plugins/AutoRole/config.yaml`, schema `ar/config/ConfigSerializer.kt:6-24`, strict kaml decoding (unknown keys ⇒ error):

| Key | Type | Default | Validation / use |
|---|---|---|---|
| `enabled` | Boolean | `false` | Master switch; handler returns immediately when false. |
| `guilds` | List<GuildConfig> | **required** (no default; missing ⇒ decode error ⇒ startup abort) | — |
| `guilds[].guild_id` | Long | required | `require(guildId > 0)` (`ConfigSerializer.kt:20`) |
| `guilds[].role_ids` | List<Long> | required | `require(roleIds.isNotEmpty())` (`ConfigSerializer.kt:21`) |

Shipped default (`src/main/resources/config.yaml`) — note real production IDs are hard-coded:
```yaml
enabled: false
guilds:
  - guild_id: 858672865355890708
    role_ids:
      - 858672865385119755
      - 858701368457953360
      - 858707058530451476
      - 858703314606751764
      - 858704345448841226
      - 858672865385119757
```

## 7. Localization & templates

None (no `lang/`, no MessageCreator, no placeholders, no user-visible text).

## 8. Persistence

None (config only). Migration: the port must read the same `config.yaml` shape (`enabled`, `guilds[].guild_id`, `guilds[].role_ids`), keeping 64-bit IDs as integers.

## 9. External dependencies

Gradle: only `compileOnly(project(":Core"))`. Uses `BotLoader.jdaBot` directly (`ar/AutoRole.kt:5`). No HTTP, no credentials, no plugin dependencies.

## 10. Discord requirements

- Privileged intent **GUILD_MEMBERS** (member join events) — enabled unconditionally by Core (`core/base/BotLoader.kt:68-72`), not declared in info.yaml.
- Role cache (always available in JDA); member cache not required.
- Bot permission `Manage Roles` in each configured guild, and the bot's top role must be above every configured role; configured roles must not be managed or `@everyone`.
- Rate-limit: one member PATCH per join in tracked guilds; raids ⇒ bursts against the per-guild member-modify bucket (JDA queues them).

## 11. Concurrency

- Handler runs on JDA's single event thread.
- `trackedGuildIds` and `addRoles` are two plain `private var`s reassigned separately by `reload()` on the dashboard's Ktor thread (`ar/AutoRole.kt:14-19`): a join processed between the two assignments can see a new guild id with the old map ⇒ `getValue` throws `NoSuchElementException` (tiny window). No `@Volatile`.
- Object initialization is lazy and thread-safe (JVM class init).

## 12. Bugs, quirks, dead code, hard-coded values

Behavior to preserve:
- Roles applied only to guilds listed in config; nothing happens in other guilds.
- Applied on every join, including bots and re-joins.
- Unknown/missing role IDs silently ignored.
- Config validation: `guild_id > 0`, `role_ids` non-empty, `guilds` required even when disabled.

Probable bugs / risks:
1. Replace semantics (`modifyMemberRoles(member, roles)`) instead of additive add — can strip roles assigned concurrently (`ar/AutoRole.kt:24`).
2. Global role lookup (`jdaBot.getRoleById`) lets a role ID from another guild into the list ⇒ `IllegalArgumentException` ⇒ the whole assignment fails for that guild (`ar/AutoRole.kt:11`, `:17`).
3. Any single bad role (managed / above bot) blocks all roles for the member (all-or-nothing client-side checks).
4. Role entities captured once; changes in Discord (role deleted/recreated, bot permission changes) need a dashboard reload or restart.
5. Split non-atomic reassignment race (§11).
6. Load doesn't pre-validate roles (errors appear only at the first join); no log of skipped/unresolved role IDs.
7. Shipped default config contains real guild/role IDs (`src/main/resources/config.yaml:3-10`).

Dead code: none. TODOs: none.

## 13. Testability

Pure logic:
- Config parsing/validation (pydantic): required `guilds`, `guild_id > 0`, non-empty `role_ids`, strict/unknown-key policy.
- `build_role_plan(config, guild) -> list[role]` (resolve IDs within the guild, drop missing; decide policy for managed/too-high roles — skip individually vs fail all).
- `should_apply(guild_id, tracked)`.

Discord doubles: `Member` (guild, roles, `edit`/`add_roles` spy), `Guild.get_role`, bot top role / permissions for hierarchy tests; `on_member_join` dispatch.

## 14. Porting assessment

Difficulty: **Low**.

discord.py mapping: a `Cog` with `@commands.Cog.listener() async def on_member_join(member)`; `Intents.members = True`. Resolve roles with `member.guild.get_role(id)` (guild-scoped, avoids bug 2). For one request with the original effect use `await member.edit(roles=roles)` (replace, identical to JDA) or `await member.add_roles(*roles, atomic=False)` (one PATCH computed from cache = additive); note `add_roles(..., atomic=True)` (default) issues one request per role. discord.py does not do JDA's client-side hierarchy/managed checks — expect `discord.Forbidden`/`HTTPException` and log them. Resolve roles at join time (no stale references) unless parity with "resolve once at init" is required.

Risks: choosing add vs replace semantics (document); per-role vs single request; error-handling parity (JDA throws before sending, discord.py gets HTTP errors).
