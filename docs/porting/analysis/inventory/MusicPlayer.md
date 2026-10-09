# MusicPlayer: porting inventory (branch `main`, HEAD 3a59607)

Repo root: `/Users/xinshou/IdeaProjects/XsDiscordBotKt`.
Path conventions used below:

- Bare file names such as `MusicPlayer.kt:123` are relative to `Plugins/MusicPlayer/src/main/kotlin/musicplayer/` (sub-packages are written out: `music/…`, `util/…`, `command/…`, `config/…`, `model/…`).
- `res:` = `Plugins/MusicPlayer/src/main/resources/`
- `core:` = `Core/src/main/kotlin/core/`
- `log:` = `DevServer/log/output.log`. This is a real run on 2026-04-07 (not part of the source, but it shows the observed behaviour).

Anything not verified is marked **(unverified)**.

---

## 1. Overview

| Item | Value |
|---|---|
| Path | `Plugins/MusicPlayer` |
| Kotlin files / LOC | **11 files, 2,721 lines** (`wc -l`), about 2,118 non-blank, non-comment |
| Per file | `MusicPlayer.kt` 957 · `music/GuildMusicManager.kt` 342 · `util/MusicPlayerUtils.kt` 312 · `config/ConfigSerializer.kt` 297 · `music/HistoryIndexManager.kt` 252 · `command/Register.kt` 154 · `Event.kt` 140 · `music/TrackSchedulerCompat.kt` 127 · `music/AudioPlayerSendHandler.kt` 58 · `command/CmdFileSerializer.kt` 56 · `model/TrackInfo.kt` 26 |
| Resources | `config.yaml` (103 lines), `info.yaml`, `lang/{en-US,zh-TW}/register.yaml`, and `lang/{en-US,zh-TW}/message/{now-playing,pause,play,queue,resume,skip,volume}.yaml` (16 YAML files). `images/` holds 15 files (5 `.webp` progress-bar segments and 10 `.png` media icons). The images ship in the jar, but **no code exports or uploads them**; the owner has to upload them by hand as application emojis. |
| Purpose | A per-guild music player. Slash commands join or leave voice, play YouTube (search or URL), SoundCloud, optionally Spotify, and other lavaplayer sources, and provide pause, resume, stop, skip, volume, queue, shuffle and now-playing. Command responses are an ephemeral "player panel" that refreshes itself and carries 5 control buttons. |
| Entry object | `object Event : PluginEventConfigure<ConfigSerializer>(true, ConfigSerializer.serializer())` (`Event.kt:16`), package `tw.xinshou.discord.plugin.musicplayer` |
| Listener flag | `true`, so the object is registered as a JDA `ListenerAdapter` |
| Logic singleton | `object MusicPlayer` (`MusicPlayer.kt:56`). It is initialized lazily on first access (first slash, button or autocomplete event, or a reload). Observed: `MusicPlayer.<clinit>` ran on the first `/join` (log:795→812). |
| info.yaml (`res:info.yaml`) | `author/name/coreApi/version` are Gradle-expanded (`name`=`MusicPlayer`, `coreApi`=`3.4`, version `3.4.x[-SNAPSHOT]`) · `main: tw.xinshou.discord.plugin.musicplayer.Event` · `depend_plugins: [AudioAPI]` · `require_intents: [GUILD_VOICE_STATES]` · `require_cache_flags: [VOICE_STATE]` · `require_member_cache_policies: [VOICE]` · no `soft_depend_plugins`, `depend_jars`, `prefix` (defaults to `MusicPlayer`, unused) or `component_prefix`. Core therefore derives the component prefix **`musicplayer@`** (`core:base/PluginLoader.kt:277-285`, lowercase name + `@`) and logs WARN "Plugin name 'MusicPlayer' is too long…" because the name is longer than 10 characters (log:448). |

---

## 2. Lifecycle

### load() (`Event.kt:19-35`)
1. `super.load()` (`core:plugin/PluginEvent.kt:23-29,59-65`):
   - Exports the jar's `lang/` to `plugins/MusicPlayer/lang/`. Only missing files are written unless the CLI flag `-Flang` is set.
   - Reads `plugins/MusicPlayer/config.yaml`, exporting the default first if it is missing, and decodes it with **kaml in strict mode**. Unknown keys raise an error.
   - The data-class `require(...)` checks run during decoding, **even when `enabled: false`**.
2. `1` (`Event.kt:21`) is a stray no-op expression.
3. If `!config.enabled`, it logs WARN `MusicPlayer is disabled.` and returns. The localizer is never built, so `guildCommands()` returns an empty array.
4. It builds `StringLocalizer(pluginDir, defaultLocale = en-US, CmdFileSerializer)` from `lang/*/register.yaml`.
5. It calls `config.validate()` (cross-field rules, §6). Failures throw `IllegalStateException`. `PluginLoader.run()` does not catch them (`core:base/PluginLoader.kt:145-155`), so **the whole bot fails to start**.
6. It logs INFO `MusicPlayer plugin loaded successfully`.
- Load order quirk (Core): `PluginLoader.run()` iterates `pluginQueue.values.reversed()`, so **MusicPlayer.load() runs before its dependency AudioAPI.load()** (log:674 then log:757).

### unload() (`Event.kt:37-44`)
- It only logs two INFO lines. It does **not** stop players, close voice connections (JDA shutdown does that), shut down `messageUpdateScheduler`, call `playerManager.shutdown()`, or clear any maps.
- `GuildMusicManager.cleanup()` (`music/GuildMusicManager.kt:308-326`) exists but is never called.

### reload() (`Event.kt:46-62`)
1. `super.reload()` re-exports missing lang files and re-reads the config.
2. If disabled, it logs WARN and returns. Playback, voice connections and panel refresh tasks **keep running**; the commands disappear at the next command refresh.
3. Otherwise it runs `validate()`, builds a new localizer, and calls `MusicPlayer.reload()` (`MusicPlayer.kt:140-147`). That method creates a new `MessageCreator`, which re-reads the templates, and clears `searchCache`.
- Reload does **not** refresh:
  - registered audio sources (Spotify on/off and credentials are read only once, at object init);
  - the application emoji mentions (`MusicPlayerUtils` reads them once);
  - existing `GuildMusicManager`s (volume, loop mode and history survive);
  - tracked panels.

### `MusicPlayer` object init (`MusicPlayer.kt:56-138`)
- `ComponentIdManager(prefix = componentPrefix, idKeys = {"action": STRING})` (`MusicPlayer.kt:58-63`).
- `MessageCreator(pluginDir, defaultLocale = zh-TW, componentIdManager)` (`MusicPlayer.kt:65-69`).
- `DefaultAudioPlayerManager()` with lavaplayer defaults: loader pool max 10, frame buffer 5 s, stuck threshold 10 s, player-cleanup threshold 1 min (lavaplayer source, main branch).
- Source registration order. The first source that recognises an identifier wins:
  1. `dev.lavalink.youtube.YoutubeAudioSourceManager(allowSearch = true, allowDirectVideoIds = true, allowDirectPlaylistIds = true)` (`MusicPlayer.kt:88-94`)
  2. `SoundCloudAudioSourceManager.createDefault()` (`MusicPlayer.kt:98`)
  3. lavasrc `SpotifySourceManager(null /*providers → default YouTube mirroring*/, clientId, clientSecret, countryCode, playerManager)`, **only if `engines.spotify.enabled`** (`MusicPlayer.kt:102-116`). On failure it logs WARN and continues.
  4. `AudioSourceManagers.registerRemoteSources(playerManager)` with **no exclusions** (`MusicPlayer.kt:120`). Per lavaplayer's source (main branch; 2.2.6 assumed the same, **unverified**) this adds:
     - lavaplayer's **deprecated built-in YouTube** manager
     - Yandex Music
     - SoundCloud (a second time)
     - Bandcamp
     - Vimeo
     - Twitch
     - Beam
     - Getyarn
     - Niconico
     - generic **HTTP**
  5. `AudioSourceManagers.registerLocalSource(playerManager)`, i.e. **local filesystem** (`MusicPlayer.kt:127`).
  - An exception in steps 1 or 2 is rethrown. The object init then fails with `ExceptionInInitializerError` and the plugin stays broken until restart.
- These config keys are ignored here: `engines.youtube.*` and `engines.soundcloud.*`. YouTube and SoundCloud are always registered.

### `MusicPlayerUtils` object init (`util/MusicPlayerUtils.kt:51-65`)
- The first access (e.g. `isUserInVoiceChannel` at the start of `/play`, or the button handler) makes a **blocking** `jdaBot.retrieveApplicationEmojis().complete()` call. It stores `asMention` for the 9 emoji names in `config.emojis`.
  - Observed on the first `/join` after startup: Core's defer callback returned at 19:10:03.705 (log:815), and `GET /applications/{id}/emojis` completed at 19:10:09.742 (log:820). That is about 6 s of blocking on the JDA event thread. A later run took about 0.5 s (log:2278→2283).
- If that REST call fails, the result is `ExceptionInInitializerError`. That is an `Error`, which `Event`'s `catch (e: Exception)` does not catch. The user gets no response and the plugin stays broken until restart.
- If a name has no matching emoji, its `lateinit var` stays unset, and rendering later throws `UninitializedPropertyAccessException`.

### Background jobs
| Job | Location | Schedule | Action |
|---|---|---|---|
| Panel refresher | `MusicPlayer.kt:83` (`Executors.newScheduledThreadPool(2)`), `MusicPlayer.kt:181-183` | One `scheduleAtFixedRate` per tracked panel: initial delay 5 s, period 5 s. The task is **never cancelled**. | `updateTrackedMessage(messageId)`: deletes the panel when ≥60 s have passed since `lastInteractionTime`, otherwise re-renders it (§4) |
| Idle check | `music/GuildMusicManager.kt:69-112` | Would run every 1 min after a 10-min delay, but `idleCheckScheduler` is always `null`. The constructor default at `music/GuildMusicManager.kt:24` is used because `MusicPlayer.kt:777` passes only 2 args. | **Never runs** (dead code) |
| lavaplayer internals | `DefaultAudioPlayerManager` | Library threads | Loading, decoding, Opus re-encoding (when volume ≠ 100, log:3618), and player cleanup after 1 min without `provide()` polls (`CLEANUP`, `mayStartNext=false`) |

### State held in memory (nothing is persisted)
- `musicManagers: ConcurrentHashMap<Long guildId, GuildMusicManager>` (`MusicPlayer.kt:72`).
  - Created by `getGuildAudioPlayer` (`MusicPlayer.kt:774-781`), which runs on **every** slash command, every button press and every volume autocomplete for the guild. It also re-sets `guild.audioManager.sendingHandler` each time.
  - Entries are never removed.
- Per guild (`GuildMusicManager`):
  - the lavaplayer `AudioPlayer`: volume, paused flag, playing track;
  - `HistoryIndexManager`: `history: MutableList<AudioTrack>` (≤240) and `historyIndex: AtomicInteger`;
  - `TrackSchedulerCompat`: `sequentialPlayback` / `singleTrackLoop` booleans;
  - unused statistics counters, `lastActivityTime`, and the `AudioPlayerSendHandler`.
- `searchCache` (`MusicPlayer.kt:73-78`) is a synchronized `LinkedHashMap`. It evicts in insertion order (FIFO, not LRU) once it holds more than **100** entries. The key is the raw autocomplete input. There is no TTL. It is cleared on reload.
- `trackedMessages: ConcurrentHashMap<String, TrackedMessage>` uses the key `"{guildId}-{channelId}-{interactionId}"` (`MusicPlayer.kt:157`). `TrackedMessage` (`MusicPlayer.kt:47-54`) holds hook, template key, locale, member, manager and `lastInteractionTime`.
- `userTrackedMessages: ConcurrentHashMap<userId, messageId>` (`MusicPlayer.kt:82`) is keyed by **user id only, not by guild**.
- Side effect: music placeholders are written into Core's shared, cached per-member `Substitutor` (`Placeholder.get(member)`, §7/§12).

---

## 3. Slash commands and context menus

### Common to all 11 commands
- **Guild** commands. `Event.guildCommands()` → `command/Register.kt:78-155`. Core pushes the full set to every guild at startup and on `GuildJoin` (`core:base/ListenerManager.kt:18-36`). The array is empty when disabled, which removes the commands at the next refresh.
- `setDefaultPermissions(DefaultMemberPermissions.ENABLED)`, i.e. usable by everyone. No NSFW. No subcommands or groups. **No context menus.**
- Localizations come from `lang/<locale>/register.yaml` through `StringLocalizer`. The flattened keys use **Kotlin property names**: `join.name`, `play.options.query.name`, and `nowPlaying.*` for YAML `now_playing` (`command/Register.kt:72-75`). Locales are `en-US` (default) and `zh-TW`. The base (unlocalized) descriptions are hard-coded English in `command/Register.kt` and **differ** from the en-US ones.
- Routing: `config.enabled && event.name ∈ {join, disconnect, play, pause, resume, stop, skip, volume, queue, shuffle, now-playing}` (`Event.kt:72-74`, `command/Register.kt:11-23`).
- **Response model.**
  - Core's `InteractionLogger` (registered before the plugin listeners) has already called **`deferReply(true)` (ephemeral)** (`core:logger/InteractionLogger.kt:25-30`). It is on by default; `--no-auto-defer-interactions` disables it.
  - MusicPlayer never acknowledges an interaction itself. It only uses `event.hook.editOriginal(…)` and `event.hook.deleteOriginal()`, so **every response is ephemeral**.
  - If auto-defer is disabled, all MusicPlayer commands hang, because hook calls wait for an acknowledgement that never comes.
- Pre-dispatch (`MusicPlayer.kt:278-296`): a null guild or member makes the handler return silently, leaving "thinking…". Then `getGuildAudioPlayer(guild)` runs.
- Exceptions thrown synchronously in a handler (`Event.kt:79-93`):
  - Logged at ERROR.
  - The message is `❌ 處理指令時發生錯誤：{e.message}` when `messages.show_detailed_errors` (default `true`), otherwise `❌ 處理指令時發生錯誤，請稍後再試`.
  - It is delivered with `hook.editOriginal` if the interaction is acknowledged, otherwise as an ephemeral `reply`.
  - `Error`s are not caught.
- **Every user-facing string in the handlers is hard-coded zh-TW** regardless of user locale. Only the template footer and volume text are localized.

### Command table
| Command | Base description (code) | en-US name / desc | zh-TW name / desc | Options |
|---|---|---|---|---|
| `join` | Make the bot join your voice channel | join / Make the bot join your current voice channel | 加入 / 讓機器人加入您所在的語音頻道 | none |
| `disconnect` | Make the bot leave the voice channel | disconnect / Make the bot leave the current voice channel | 離開 / 讓機器人離開目前的語音頻道 | none |
| `play` | Play music | play / Play a specified song or add it to the queue | 播放 / 播放指定的歌曲或將其加入佇列 | `query` STRING **required**, max_length 500, **autocomplete**. Base desc "Song name, artist, or URL"; en-US **name "song"** / "Enter a song's YouTube/Spotify URL or keyword"; zh-TW 歌曲 / 輸入歌曲的 YouTube/Spotify 網址或關鍵字 |
| `pause` | Pause the currently playing music | pause / Pause the currently playing song | 暫停 / 暫停目前正在播放的歌曲 | none |
| `resume` | Resume the paused music | resume / Resume the paused song | 繼續 / 繼續播放已暫停的歌曲 | none |
| `stop` | Stop playing and clear the playlist | stop / Stop the playback and clear the entire queue | 停止 / 停止播放並清空整個佇列 | none |
| `skip` | Skip the currently playing song | skip / Skip the currently playing song | 跳過 / 跳過目前播放的歌曲 | `count` INTEGER optional, min 1, max 50. Base "Number of songs to skip (default is 1)"; en-US **name "amount"** / "The number of songs to skip (default is 1)"; zh-TW 數量 / 要跳過的歌曲數量 (預設為 1) |
| `volume` | Set the player volume | volume / Adjust the playback volume | 音量 / 調整播放音量 | `level` INTEGER **required**, min 0, max 100, **autocomplete**. Base "Volume level (0-100)"; en-US level / "Set the volume level (0-100)"; zh-TW 大小 / 設定音量大小 (0-100) |
| `queue` | View the current playlist | queue / View the current song queue | 待播清單 / 查看目前的歌曲播放佇列 | none |
| `shuffle` | Shuffle the current playlist once | shuffle / Shuffle the current song queue | 打亂播放清單 / 打亂目前的歌曲播放佇列 | none |
| `now-playing` | View detailed information of the currently playing song | now-playing / Display information about the currently playing song | 正在播放 / 顯示目前正在播放的歌曲資訊 | none |

### Per-command behaviour
"Tracked" means the response becomes a self-refreshing panel (§4 "Panel tracking"). "Unacked" is not relevant here: slash commands are always acked by Core.

**`/join`** (`MusicPlayer.kt:335-349`)
1. `validateVoiceState` (`util/MusicPlayerUtils.kt:97-109`) checks, in order:
   - member null → `❌ 無法獲取用戶資訊`
   - guild null → `❌ 無法獲取伺服器資訊`
   - user not in any voice channel → `❌ 您必須先加入語音頻道才能使用此功能！`
   - channel is not a `VoiceChannel` (e.g. a Stage) → `❌ 無法找到您的語音頻道！`

   The `❌ ` prefix is added at `MusicPlayer.kt:338`.
2. `audioManager.openAudioConnection(channel)`. If it throws, the reply is `❌ 無法連接到語音頻道！`. Examples are a JDA permission exception for missing CONNECT, or a full channel without Move Members (JDA behaviour, **unverified** for 6.4.1). There is no pre-check. The connection is **asynchronous**, so later failures are not reported. If the bot is already in another channel, it moves (JDA). It joins with `self_deaf:false, self_mute:false` (log:825).
3. On success it calls `hook.deleteOriginal()`. The "thinking…" indicator disappears and the user sees **no confirmation** (log:863, DELETE webhook).

**`/disconnect`** (`MusicPlayer.kt:352-363`)
1. `!guild.audioManager.isConnected` → `❌ 機器人目前沒有連接到任何語音頻道！`
2. Otherwise:
   - `musicManager.stop()`: clears the history and index, then calls `stopTrack()`. The **paused flag is not reset**.
   - `closeAudioConnection()`
   - `deleteOriginal()`
- No voice-channel check on the user: **any member can disconnect the bot**.

**`/play query`** (`MusicPlayer.kt:365-471`)
1. User not in voice → `❌ 您必須先加入語音頻道才能播放音樂！`
2. User's channel is not a `VoiceChannel` (Stage) → `❌ 無法找到您的語音頻道！`
3. The bot lacks `VOICE_CONNECT` in the **user's** channel → `❌ 機器人沒有連接到該語音頻道的權限！`. This is checked even when the bot is already connected elsewhere and will not move. SPEAK is never checked.
4. `query` null or blank → `❌ 請提供要播放的歌曲名稱或URL！`
5. If the bot is not connected, it connects to the user's channel; failure → `❌ 無法連接到語音頻道！`. **If the bot is already connected elsewhere, it does not move and the track goes into the existing session.** There is no same-channel requirement.
6. Identifier routing (`MusicPlayer.kt:401-407`). The logic is the same as the dead `MusicPlayerUtils.processSearchQuery`:
   - `startsWith("http")` → passed as-is
   - contains `youtube.com`, `youtu.be`, `soundcloud.com` or `spotify.com` → passed as-is
   - anything else → `"ytsearch:" + query`
7. `playerManager.loadItemOrdered(musicManager, identifier, handler)` loads asynchronously, ordered per guild. The handler cases:
   - `trackLoaded(t)`:
     - Calls `musicManager.playTrack(t, member)`; the boolean result is **ignored**.
     - Edits the original message to the **`play`** template, rendered for the **loaded** track. That may be a queued track rather than the one playing; the first refresh 5 s later switches the panel to the *currently playing* track.
     - On a successful edit it starts tracking the panel.
   - `playlistLoaded(pl)`:
     - Empty → `❌ 播放清單為空！`
     - If the identifier starts with `ytsearch:`, `scsearch:` or `ytmsearch:`, only `tracks.first()` is queued. Since the user's own input is always prefixed with `ytsearch:`, only `ytsearch:` occurs in practice.
     - Otherwise **every** track is queued in order. `selectedTrack` is ignored, `max_queue_size` is ignored, and the 240 history cap silently drops overflow.
     - The panel is rendered for `tracks.first()` and tracked.
   - `noMatches()` → `❌ 找不到符合的歌曲：{raw query}`
   - `loadFailed(ex)` → `❌ 載入歌曲時發生錯誤：{ex.message}`, plus an ERROR log.
   - An exception thrown *inside* these callbacks (e.g. a missing emoji) is caught and logged by lavaplayer and **not** routed to `loadFailed` (lavaplayer `DefaultAudioPlayerManager.submitItemToResultHandler`). The user keeps seeing "thinking…", but playback may already have started.
8. Enqueue (`music/GuildMusicManager.kt:127-164` → `music/HistoryIndexManager.kt:41-74`):
   - A blank title is rejected.
   - `track.userData` is set to `Map{requesterId, requesterName = member.effectiveName, requesterUsername = user.name, requesterAvatarUrl = member.effectiveAvatarUrl}`.
   - A **clone** is appended to `history`.
   - **Playback starts only if `history` was empty** (index ← 0, `startTrack(…, noInterrupt = false)`). Otherwise the track is only appended, and `manageHistorySize()` runs. See bug B1.

**`/pause`** (`MusicPlayer.kt:473-502`)
- No playing track (`audioPlayer.playingTrack == null`) → `❌ 目前沒有正在播放的歌曲！`
- Already paused → `⏸️ 歌曲已經暫停了！`
- Otherwise it pauses and renders the **`pause`** template (gold `0xba9c55`, pause emoji in the bar). Tracked. No voice check.

**`/resume`** (`MusicPlayer.kt:504-533`)
- No track → `❌ 目前沒有正在播放的歌曲！`
- Not paused → `▶️ 歌曲已經在播放了！`
- Otherwise it resumes and renders **`resume`** (green `0x68c06e`). Tracked. No voice check.

**`/stop`** (`MusicPlayer.kt:535-547`)
- No playing track **and** an empty upcoming list → `❌ 目前沒有正在播放的歌曲！`
- Otherwise `stop()`, then `closeAudioConnection()` (**`/stop` also disconnects**), then `deleteOriginal()`. No voice check. The paused flag is not reset.

**`/skip [count=1]`** (`MusicPlayer.kt:549-607`)
- No playing track → `❌ 目前沒有正在播放的歌曲！`
- `count ≤ 0` → `❌ 跳過數量必須大於 0！`. Discord enforces min 1, so this is unreachable.
- Let `max = upcomingCount + 1`. `count > max` → `❌ 只能跳過 {max} 首歌曲！`
- It then calls `musicManager.skip()` `count` times and stops at the first `false` (no next track). `skip()` unpauses and starts a clone of `history[++index]` (`music/GuildMusicManager.kt:217-237`, `music/HistoryIndexManager.kt:76-101`).
- It then reads the playing track:
  - `null` → `⏭️ 已跳過歌曲，播放清單已結束`. This is practically unreachable, because skipping never stops the last track.
  - Otherwise it renders **`skip`** for the new track. Tracked.
- An exception → `❌ 跳過歌曲時發生錯誤`.
- **Effective semantics:** skipping while on the last track is a no-op that re-shows that track, and `count = max` behaves like `count = max-1`. No voice check.

**`/volume level`** (`MusicPlayer.kt:609-635`)
- Reads `before = getVolume()`, then `setVolume(level)` (0..100, otherwise `false`; the result is ignored).
- Renders **`volume`** with `music_player@player_volume_before/after`. Those values are written via `Placeholder.get(member).putAll`. Tracked: it only refreshes while a track is playing and is deleted at 60 s.
- No voice check. The volume persists per guild in memory until restart (it is not reset by `/stop`).

**`/queue`** (`MusicPlayer.kt:637-680`)
- No playing track **or** an empty upcoming list → `❌ 播放清單為空！`. This includes the case where a song is playing and nothing is queued.
- Otherwise it builds an embed:
  - colour `0x9bd9d5`;
  - upcoming tracks in chunks of 10, one field per chunk, field name `—` (U+2014), `inline=false`;
  - each line `"{n}. **{title}** | {author} `[{formatTime(length)}]`"`, with `n` starting at 1 for the next track and live streams shown as `∞ (直播)`;
  - **no pagination or size guard** (Discord limits: 25 fields, 1024 per value, 6000 total).
- Renders **`queue`** with `modelMapper {"%music_player@player_track_list_model_key%": embed}`. Tracked, but **refreshes always fail silently** (B6).

**`/shuffle`** (`MusicPlayer.kt:707-731`)
- User not in any voice channel → `❌ 您必須在語音頻道中才能使用此指令！`
- Upcoming list ≤ 1 → `❌ 播放清單中沒有足夠的歌曲可以打亂！（至少需要2首歌曲）`
- `shuffleQueue()` applies a random permutation to the **upcoming tracks only** (history is unchanged) (`music/HistoryIndexManager.kt:216-244`). Replies are plain text `🔀 已成功打亂播放清單！共打亂了 {n} 首歌曲。` or `❌ 打亂播放清單失敗！`. **Not tracked.**

**`/now-playing`** (`MusicPlayer.kt:682-705`)
- No track → `❌ 目前沒有正在播放的歌曲！`
- Otherwise it renders **`now-playing`**. Tracked. No voice check.

### Autocomplete (`Event.kt:120-140`, `MusicPlayer.kt:235-276`)
- **Event filter is `config.enabled` only.** Every autocomplete interaction in the whole bot reaches this handler. Anything other than `play/query` or `volume/level` is answered with **`replyChoices([])`**, which would break other plugins' autocomplete (B7). On exception it answers `[]`.
- `play/query`:
  - Input shorter than 2 characters → `[]`.
  - Otherwise `searchYouTube(input)`:
    - Checks `searchCache[input]` first.
    - On a miss, `loadItem("ytsearch:" + input)`: `trackLoaded` → 1 result; `playlistLoaded` → first 10; `noMatches` or `loadFailed` → `[]`.
    - `.orTimeout(10 s)`. This exceeds Discord's ~3 s autocomplete deadline; a late answer fails asynchronously.
  - Choices are the first 10: name `"{title} | {author}".take(100)`, **value = track URI**.
  - A URL typed into the field is searched as text (`ytsearch:https://…`, log:3570).
- `volume/level`: a single choice, name `當前音量: {current}`, value = current volume. As a side effect it creates the guild manager.

---

## 4. Components

### custom_id format
`ComponentIdManager` builds `{prefix}{shortKey}:{value}`. The prefix is `musicplayer@` and the only key is `action`, mapped to short key `a` (`core:util/ComponentIdManager.kt:124-143`). The resulting IDs are exactly:

| custom_id | Button style | Emoji (template literal) |
|---|---|---|
| `musicplayer@a:previous` | 2 SECONDARY | `<:music_player__media_previous:1395593807352954950>` |
| `musicplayer@a:pause-resume` | 2 SECONDARY | `<:music_player__media_pause_resume:1395593823916265524>` |
| `musicplayer@a:skip` | 2 SECONDARY | `<:music_player__media_next:1395593814684471307>` |
| `musicplayer@a:loop` | 2 SECONDARY | `%music_player@player_currnet_loop_mode_emoji%` → the `media_ordered` or `media_repeat_once` app emoji |
| `musicplayer@a:disconnect` | 4 DANGER | `<:music_player__media_disconnect:1395595107255844915>` |

- All five buttons sit in one action row, with no labels and `disabled: false`.
- They appear on the `play`, `pause`, `resume`, `skip`, `now-playing` and `queue` templates (`res:lang/*/message/*.yaml`). `volume` has no components.
- The 4 literal emoji IDs belong to the author's bot application and must be replaced for any other bot.
- There are no select menus, modals or text inputs.

### Routing and permissions
- `Event.kt:96-118` dispatches when `config.enabled` holds and `componentId.startsWith("musicplayer@")`. It then calls `componentIdManager.parse` and switches on `action`.
  - An unknown action does nothing. The interaction is never acknowledged, so the client shows "This interaction failed".
  - A parse error or other exception → `❌ 處理按鈕互動時發生錯誤：{msg}` / `…，請稍後再試`.
- **Who can click:**
  - Panels are ephemeral, so only the user who ran the command can see and click them.
  - The handler also requires the clicker to be in *some* voice channel, not necessarily the bot's (`MusicPlayer.kt:306-309`).
  - That rejection, `❌ 您必須在語音頻道中才能控制音樂播放！`, is sent through `hook.editOriginal` **without acknowledging first**. JDA holds hook requests until the interaction is acknowledged (JDA docs), so it is never shown; the user sees "This interaction failed" (B3).
- The buttons are **stateless**. They act on the guild's *current* player, whatever track the panel showed.

### Actions
- **previous** (`MusicPlayer.kt:792-842`, `music/HistoryIndexManager.kt:110-157`). It **calls `deferEdit()` first**.
  - No history entry at the index → error `沒有正在播放的歌曲`.
  - Player idle → `無法獲取當前播放狀態`.
  - No previous track **or** position ≥ **5000 ms** → restart the current track from 0 (`TrackRestarted`).
  - Otherwise start a clone of `history[index-1]` and decrement the index (`PreviousTrackPlayed`).
  - On success it edits the panel to **`now-playing`**, rendered for the *history entry* (not the playing clone), so the bar shows 00:00.
  - On error it edits the content to `❌ {message}`. Embeds and buttons stay until the next full render.
  - A catch-all error → `❌ 處理前一首按鈕時發生錯誤`.
  - The paused flag is **not** cleared.
- **pause-resume** (`MusicPlayer.kt:844-876`)
  - No track → `❌ 目前沒有正在播放的歌曲！` (unacked).
  - Otherwise toggles via `isPaused()`. A `false` result → `❌ 操作失敗` (unacked).
  - On success: `deferEdit()`, then edit to `now-playing` for the playing track (colour and play/pause emoji reflect the new state).
- **skip** (`MusicPlayer.kt:878-906`)
  - No track → `❌ 目前沒有正在播放的歌曲！` (unacked).
  - `skip()` returns false (no next track) → `❌ 沒有更多歌曲可播放` (unacked).
  - Next track null → `⏭️ 已跳過歌曲，播放清單已結束` (unacked).
  - Otherwise `deferEdit()`, then edit to `now-playing` for the new track.
- **loop** (`MusicPlayer.kt:908-942`)
  - Toggles **sequential ↔ single-track loop**. The state changes even when nothing is playing.
  - With no current track it returns with **no acknowledgement**.
  - Otherwise `deferEdit()`, then edit to `now-playing` with the new loop emoji.
- **disconnect** (`MusicPlayer.kt:944-956`)
  - Not connected → `❌ 機器人目前沒有連接到任何語音頻道！` (unacked).
  - Otherwise `stop()`, `closeAudioConnection()`, `deferEdit()`, then `deleteOriginal()` (the panel is removed).

### Panel tracking (`MusicPlayer.kt:150-233`)
- **Start:** after the edit succeeds for `play`, `pause`, `resume`, `skip`, `volume`, `queue` and `now-playing` (not `shuffle`, `join`, `disconnect` or `stop`):
  - If the same **user id** already has a tracked panel (in *any* guild), that panel is deleted (`hook.deleteOriginal()`). There is **one live panel per user**.
  - The new panel is recorded and a fixed-rate 5 s task is scheduled.
- **Each tick:**
  - If `now − lastInteractionTime ≥ 60 000 ms`, delete the panel and remove both map entries.
  - Otherwise, if a track is playing, re-render the panel's *original template key* for the **current** track and edit it. Exceptions are swallowed silently. When nothing is playing, the panel is left untouched.
- **Expiry:** about 60 s after creation. Button clicks were meant to extend it, but `updateLastInteractionTime(event.hook)` builds its key from the *button* interaction id (`MusicPlayer.kt:230-233,304`), so it never matches and **the panel always dies about 60 s after creation** (B4).
- Observed: 12 edits at roughly 5 s intervals, then deletion (log:3616 onward, 20:14:30 → 20:15:31).
- Task leak: deleted panels' tasks keep firing every 5 s forever (B5).

---

## 5. Events

| Event | Filter | Behaviour |
|---|---|---|
| `onSlashCommandInteraction` (`Event.kt:72-94`) | enabled and name in the set | §3 |
| `onButtonInteraction` (`Event.kt:96-118`) | enabled and prefix `musicplayer@` | §4 |
| `onCommandAutoCompleteInteraction` (`Event.kt:120-140`) | enabled only | §3 Autocomplete. Answers unrelated autocompletes with `[]`. |
| lavaplayer `onTrackEnd` (`music/TrackSchedulerCompat.kt:32-62`) | runs only if `endReason.mayStartNext` (FINISHED, LOAD_FAILED; **not** STOPPED, REPLACED or CLEANUP) | Single-loop: `startTrack(historyCurrent.makeClone())`. Sequential (default): `HistoryIndexManager.onTrackEnd()`, which calls `skip()` if there is a next track and otherwise stays idle with the history unchanged. |
| lavaplayer `onTrackStart` (`music/TrackSchedulerCompat.kt:67-73`) | none | No-op |

- TrackException and TrackStuck are not handled.
- **No voice-state handling.** There is no `onGuildVoiceUpdate`, so nothing reacts to the bot being kicked, moved or left alone, and nothing handles `GuildLeave` or channel deletion. JDA defaults apply.
- Implicit lavaplayer behaviour: when nobody polls `provide()` (e.g. the bot was disconnected externally) for ≥1 min, lavaplayer stops the track with `CLEANUP` (`mayStartNext = false`). The player is then idle with the history non-empty, which leads into B1.

---

## 6. Configuration (`res:config.yaml`, `config/ConfigSerializer.kt`)

**Decoding:** kaml `Yaml()` runs in strict mode, so unknown keys are rejected.

**Top-level sections** with no default, which must be present: `command_message_acknowledges`, `engines`, `player`, `messages`, `features`, `performance`, `cache`, `developer`, `emojis`.

**Required fields:** no code default exists for any field of `CommandMessageAcknowledges`, `Engines/*Config` or `PlayerConfig` (including `playback` and `cache`). `Messages`, `Features`, `Performance`, `Cache`, `Developer` and `Emojis` have code defaults for every field.

`require` checks run at decode time, even when disabled. `validate()` runs only when enabled. Every failure aborts bot startup.

| Key | Type | File default | Validation | Used? |
|---|---|---|---|---|
| `enabled` | bool | `false` (code default `false`) | none | **Yes**: gates load, commands and all three listeners |
| `command_message_acknowledges.{join,disconnect,stop,play,pause,resume,skip,queue,volume,now_playing}` | bool | join/disconnect/stop `false`, the rest `true` | none | **No.** The hard-coded behaviour happens to match (join/disconnect/stop delete the response; the rest show a panel). |
| `engines.youtube.enabled` | bool | true | used in `validate()` | No (YouTube is always registered) |
| `engines.youtube.search_enabled` | bool | true | `validate()` | No |
| `engines.youtube.auto_complete` | bool | true | none | No |
| `engines.youtube.max_search_results` | int | 25 | `1..25` | No (hard-coded 10) |
| `engines.soundcloud.enabled` | bool | true | none | No (always registered) |
| `engines.soundcloud.client_id` | string | `""` | none | No |
| `engines.spotify.enabled` | bool | false | none | **Yes**: registers `SpotifySourceManager` once, at `MusicPlayer` init |
| `engines.spotify.client_id` / `client_secret` | string | dummy `"01234567890123456789012367890123"` | non-blank if enabled | **Yes** (Spotify) |
| `engines.spotify.country_code` | string | `"TW"` | length == 2 if enabled | **Yes** (Spotify) |
| `player.default_volume` | int | 40 | `0..100` | **Yes**: initial volume when a guild manager is created. Falls back to 15 if reading the config throws; coerced to 0..100 (`music/GuildMusicManager.kt:49-57`) |
| `player.auto_leave_timeout` | int ms | 600000 | ≥ 0 | **No** (no idle leave exists) |
| `player.max_queue_size` | int | 100 | > 0 | **No** (the real cap is the 240 history limit) |
| `player.search_timeout` | int ms | 30000 | > 0 | No (hard-coded 10 s) |
| `player.playback.enable_lyrics` / `show_artwork` / `show_author_avatar` | bool | true/true/true | the first two feed `validate()` | No |
| `player.playback.lyrics_preview_length` | int | 500 | > 0 | No |
| `player.cache.search_cache_size` | int | 1000 | > 0 | No (hard-coded 100) |
| `player.cache.search_cache_ttl` | int ms | 300000 | > 0 | No (no TTL) |
| `player.cache.artwork_cache_enabled` | bool | true | none | No |
| `messages.show_detailed_errors` | bool | true | none | **Yes** (`Event` error text) |
| `messages.announce_new_track` / `use_enhanced_embeds` | bool | true/true | none | No |
| `messages.embeds.show_thumbnails` / `show_progress_bar` | bool | true/false | none | No |
| `messages.embeds.color_scheme` | string | `"dynamic"` | one of {dynamic, blue, green, purple, red, orange} (the file comment lists only 4) | No |
| `features.auto_complete` | bool | true | `validate()`: true requires `engines.youtube.enabled && search_enabled`, else ISE "Auto-complete requires YouTube search to be enabled" | No (autocomplete is always on) |
| `features.lyrics_support` | bool | true | `validate()`: `enable_lyrics` requires `lyrics_support` | No |
| `features.artwork_display` | bool | true | `validate()`: `show_artwork` requires `artwork_display` | No |
| `features.multi_skip` / `volume_control` | bool | true/true | none | No |
| `performance.max_concurrent_searches` / `search_thread_pool_size` | int | 5 / 3 | > 0 | No |
| `performance.audio_send_system` | string | `"JDA"` | one of {JDA, NAS} | No (udpqueue/NAS is never wired; §9) |
| `cache.size` (MB) / `cache.expire_time` (h) | int | 100 / 24 | > 0 | No |
| `developer.debug_mode` / `log_search_queries` / `log_audio_events` | bool | false | none | No |
| `emojis.progress_white_start`, `progress_white_full`, `progress_white_end`, `progress_black`, `progress_black_end`, `media_play`, `media_pause`, `media_ordered`, `media_repeat_once` | string (application emoji **name**) | `music_player__line_white_start`, `…_line_white_full`, `…_line_white_end`, `…_line_black`, `…_line_black_end`, `music_player__media_play`, `…_media_pause`, `…_media_ordered`, `…_media_repeat_once` (code defaults are the same) | none | **Yes**: resolved once to mentions; **all 9 must exist** |

`ConfigSerializer.getEnabledSources()` and `getEnabledFeatures()` (`config/ConfigSerializer.kt:278-297`) are dead code.

---

## 7. Localization and templates

- **Locales:** `en-US`, `zh-TW`.
  - `StringLocalizer` default is en-US.
  - `MessageCreator` default is **zh-TW**. Lookup is `getOrDefault(userLocale, map[zh-TW])`, so **any locale other than en-US or zh-TW gets the zh-TW templates**, e.g. en-GB users see "由 … 點播".
- **Files:**
  - `lang/<loc>/register.yaml` feeds the command localizations (keys: `<cmd>.{name,description}`, `play.options.query.*`, `skip.options.count.*`, `volume.options.level.*`, YAML `now_playing.*`).
  - `lang/<loc>/message/{now-playing,pause,play,queue,resume,skip,volume}.yaml` are the message templates. The file name is the template key.
  - Each locale's `play`, `pause`, `resume`, `skip` and `now-playing` files are **byte-identical** (md5).
  - en-US and zh-TW differ only in the footer text and the volume title.
- **Engine:** Core **v2** `MessageCreator` (`MusicPlayer.kt:28,65-69`). The YAML uses the legacy schema (`embeds` plus `components: - !ButtonsComponent`), with no `components_v2` or `is_components_v2`, so the output is a classic embed plus an action row, **not** Components V2. A Components V2 migration (31aaae9) was reverted (b86a21c).
- **Rendering rules** inherited from Core's v1 builder (`core:builtin/messagecreator/v1/builder/MessageBuilder.kt`):
  - `title.url`, `thumbnail_url` and `footer.icon_url` are applied **only if the substituted value starts with `http`**, so an empty avatar means no footer icon.
  - A `color_code` beginning with `%` is substituted and then passed to `Color.decode`.
  - An embed field with name `""` becomes U+200B (JDA `addField` replaces blank strings with a zero-width space).
  - `model_key` lookups use the **literal** key, without substitution.
- **Templates:**

  | Key | Content |
  |---|---|
  | `play` / `pause` / `resume` / `skip` / `now-playing` | One embed. `author.name=%music_player@song_author_name%`; `title.text=%music_player@song_name%`, `url=%music_player@song_url%`; `thumbnail_url=%music_player@song_thumbnail_url%`; `footer.text` en-US `Requested by %music_player@song_requester_username%`, zh-TW `由 %music_player@song_requester_username% 點播`; `footer.icon_url=%music_player@song_requester_avatar_url%`; one field `{name:"", value:%music_player@song_duration%}`; `color_code=%music_player@player_current_color%`. Plus the 5-button row. |
  | `queue` | Embed 1: the same as above but **no footer** and a fixed colour `0x9bd9d5`. Embed 2: `model_key: "%music_player@player_track_list_model_key%"` (the queue list embed). Plus the 5-button row. |
  | `volume` | One embed, `title.text` en-US `Player volume adjusted from %music_player@player_volume_before% ➞ %music_player@player_volume_after%`, zh-TW `播放音量調整 %…before% ➞ %…after%`, colour `0x7fbf78`. No components. |

- **Placeholders defined by the plugin.** These are written into `Placeholder.get(member)` by `util/MusicPlayerUtils.getSubstitutor` (`util/MusicPlayerUtils.kt:234-304`) and by `MusicPlayer.kt:622-627`:

  | Placeholder | Source |
  |---|---|
  | `%music_player@song_author_name%` | `track.info.author` |
  | `%music_player@song_name%` | `track.info.title` |
  | `%music_player@song_url%` | `track.info.uri` |
  | `%music_player@song_thumbnail_url%` | YouTube URI → `https://img.youtube.com/vi/{videoId or identifier}/maxresdefault.jpg`. SoundCloud/Spotify → `track.getUserData(String)`, which is always null because userData is a Map. Fallback `https://i.meee.com.tw/GHexAW6.png`. |
  | `%music_player@track_duration%` | `formatTime(length)` (defined; **unused** by templates) |
  | `%music_player@song_duration%` | the progress-bar string (§13) |
  | `%music_player@song_requester_username%` | userData `requesterUsername` (fallback `未知用戶`) |
  | `%music_player@song_requester_name%` | `requesterName` (fallback `未知用戶`; unused by templates) |
  | `%music_player@song_requester_avatar_url%` | `requesterAvatarUrl` (fallback `""`) |
  | `%music_player@song_requester_id%` | `requesterId` (fallback `""`; unused) |
  | `%music_player@player_current_color%` | `"0x68c06e"` if playing (track present and not paused), else `"0xba9c55"` |
  | `%music_player@player_currnet_loop_mode_emoji%` (sic: "currnet") | `media_ordered` mention if sequential, `media_repeat_once` mention if single-loop |
  | `%music_player@player_volume_before%`, `%music_player@player_volume_after%` | the volume command |

  Core placeholders are also available through `Placeholder.get(member)` (`bot_id`, `bot_name`, `user_id`, `user_mention`, `user_name`, `user_avatar_url`, `member_display_name`, `member_avatar_url`, `member_fixed_name`), but the templates do not use them.
- **Hard-coded, non-localized strings in code:** every error and status message in §3/§4, `當前音量: ` (volume autocomplete), `∞ (直播)`, `直播中`, `未知用戶`, `—`.

---

## 8. Persistence

- **None.** There is no Mongo (`CacheDbManager`), no `JsonFileManager`/`JsonGuildFileManager`, no SQLite and no data files.
- The only files are user-editable copies exported to `plugins/MusicPlayer/config.yaml` and `plugins/MusicPlayer/lang/**` (written only if missing unless `-Flang` is set).
- State that is lost on restart: queues and history, per-guild volume, loop mode and panels.
- Migration and compatibility:
  - Decide whether the Python port reads the existing `config.yaml` with the same strict key set, and whether it honours user-customized `lang/**` files (same schema and placeholders).
  - Nothing else needs migrating.

---

## 9. External dependencies

**Gradle** (`Plugins/MusicPlayer/build.gradle.kts`):
- `compileOnly(project(":Plugins:API:AudioAPI"))`.
- `dev.lavalink.youtube:common:1.17.0`. Upstream documents the `common` module as targeting lavaplayer 1.x; the `v2` module adds thumbnails for lavaplayer 2.x. It works here at runtime (log:3570-3612).
- `com.github.topi314.lavasrc:lavasrc:4.8.1`.
- `com.github.topi314.lavasrc:lavasrc-protocol:4.8.1`. **Never referenced in code.**
- `dev.arbjerg:lavaplayer:2.2.6`.
- Repositories: `maven.lavalink.dev/releases`, `maven.topi.wtf/releases`, `jitpack.io`.
- Inherited from Core (compileOnly): JDA 6.4.1, kaml, commons-text, kotlinx-serialization.

**Network endpoints,** all reached indirectly through the libraries:
- YouTube InnerTube `youtubei.googleapis.com` (client `ANDROID_VR` observed), `*.googlevideo.com` media, and the YouTube player JS for the signature cipher (log:3570-3612).
- No YouTube OAuth, poToken or remote cipher is configured.
- SoundCloud.
- Spotify Web API (lavasrc), when enabled. Audio is mirrored through `ytsearch:` (default providers, **unverified** for 4.8.1).
- Any `http(s)` URL (lavaplayer HTTP source), Bandcamp, Vimeo, Twitch, Yandex, Niconico, Getyarn and Beam.
- The local filesystem.
- Discord REST for application emojis.

**URLs that Discord fetches for the embeds:** `https://img.youtube.com/vi/{id}/maxresdefault.jpg`, `https://i.meee.com.tw/GHexAW6.png`, and the requester's avatar CDN URL.

**Credentials:** the Spotify client id and secret (config). The SoundCloud client id is unused.

**Plugin dependencies:**
- `AudioAPI` is a **hard** dependency (`depend_plugins`). It is used only for load gating and classloader visibility; it is never called.
- No soft dependencies.
- No other plugin depends on MusicPlayer.

**Voice and DAVE:** handled entirely by Core (`core:base/BotLoader.kt:56-60`). See the Voice stack section at the end.

---

## 10. Discord requirements

- **Intents:**
  - `GUILD_VOICE_STATES` (not privileged), via info.yaml.
  - MusicPlayer itself needs none of GUILD_MEMBERS, MESSAGE_CONTENT or GUILD_PRESENCES. Core always requests GUILD_MEMBERS, SCHEDULED_EVENTS and GUILD_EXPRESSIONS (`core:base/BotLoader.kt:68-72`).
- **Cache flags:** `VOICE_STATE`.
  - Core disables it by default (`core:base/BotLoader.kt:62-67`); the plugin's `require_cache_flags` turns it back on through `enableCache` (`core:base/BotLoader.kt:74`).
  - It is required for `member.voiceState.channel`.
- **Member cache policy:** `VOICE` (Core's default set is already OWNER+VOICE).
- **Bot permissions** on the voice channel:
  - View Channel and Connect. Connect is checked only by `/play`.
  - Speak, needed to transmit but never checked.
  - Move Members, only to join a full channel (JDA-side check).
  - No text-channel permissions; all output goes through interaction webhooks.
- **Application emojis:** 13 in total.
  - 9 are resolved by name from `config.emojis`.
  - 4 are hard-coded IDs in the templates (`previous`, `pause_resume`, `next`, `disconnect`). These belong to the author's application and must be re-uploaded and re-pointed on a different bot.
  - `images/` supplies the source images. `music_player__media_loop.png` and `music_player__media_shuffle.png` are unused.
- **Rate-limit-sensitive operations:**
  - One `PATCH /webhooks/{app}/{token}/messages/@original` every 5 s per live panel (up to 12 per panel).
  - The blocking emoji fetch on first use.
  - One YouTube search per autocomplete keystroke of 2 or more characters; only exact-match cache hits avoid it.

---

## 11. Concurrency

| Thread | What runs there |
|---|---|
| JDA event threads | Command and button handlers. Calls into `HistoryIndexManager.skip`, `shuffle` and `previous`, plus `pause`, `resume` and `stop`. |
| lavaplayer loader pool | `AudioLoadResultHandler` callbacks. Calls `addTrack` and edits the panel. `loadItemOrdered(musicManager, …)` serializes loads per guild. |
| lavaplayer playback threads | `onTrackEnd`. Calls `HistoryIndexManager.onTrackEnd` → `skip`. |
| `messageUpdateScheduler` (2 threads) | Panel refresh and delete. Reads player state and mutates Core substitutors. |

Shared state and its protection:
- **`HistoryIndexManager.history`** is a plain `ArrayList` mutated from all three thread groups with no lock. `historyIndex` is an `AtomicInteger`, but check-then-act sequences (`hasNext` then `incrementAndGet`, `shuffleQueue`, `manageHistorySize`) are not atomic.
  - A user skip that races a natural track end can advance twice.
  - `ConcurrentModificationException` and index-out-of-bounds are possible, though they would be rare.
- `TrackSchedulerCompat` mode flags are plain `var`s (not volatile). `TrackedMessage.lastInteractionTime` is a plain `var`.
- The `ConcurrentHashMap`s (`musicManagers`, `trackedMessages`, `userTrackedMessages`) and the synchronized `searchCache` are safe for individual operations.
- Core's `Placeholder.get(member)` returns a **shared `HashMap`-based** substitutor. The plugin mutates it from event, loader and scheduler threads at once, so data races are possible.
- Reentrancy:
  - `HistoryIndexManager.skip()` calls itself recursively when `startTrack` fails, which in practice only happens for a null track.
  - `startTrack` dispatches `TrackEndEvent(REPLACED)` synchronously, and `mayStartNext=false` prevents a double advance. The STOPPED/REPLACED handling was fixed in 3c432c6.
- Blocking:
  - `MusicPlayerUtils` init calls `complete()` on whichever thread touches it first, typically a JDA event thread.

---

## 12. Bugs, quirks, dead code, hard-coded values

### Probable bugs (fix, but record them in the spec as known deviations)
- **B1. Playback never restarts once the history is non-empty and the player is idle** (`music/HistoryIndexManager.kt:51-68`). `addTrack` starts playback only when `history.isEmpty()`. This state arises after the queue finishes naturally, after a lavaplayer CLEANUP, or after a last track fails.
  - In that state a new `/play` is appended and never starts, yet the panel shows the track.
  - `/queue` then reports empty, `/skip` and the skip button report "nothing playing", and previous reports `無法獲取當前播放狀態`.
  - Only `/stop` or `/disconnect` clears the history and recovers. `/stop` refuses ("nothing playing") if the upcoming list is empty, and `/disconnect` refuses if the voice connection is already gone.
- **B2. The paused flag survives `/stop` and `/disconnect`.** The sequence pause → stop → play starts the new track **paused**. The reset at `music/GuildMusicManager.kt:151-154` runs after `startTrack`, when `playingTrack != null`, so it never fires. `stop()` (`music/GuildMusicManager.kt:207-211`) does not unpause.
- **B3. Button error paths edit the hook without acknowledging** (`MusicPlayer.kt:306-309, 850-852, 861-863, 880-882, 886-888, 892-894, 932, 945-947`). The user sees Discord's "This interaction failed" and never sees the text.
- **B4. Clicks never extend a panel's life.** `updateLastInteractionTime` uses the button interaction id (`MusicPlayer.kt:230-233,304`), so panels die about 60 s after creation.
- **B5. Refresh tasks are never cancelled** (`MusicPlayer.kt:181-183`). One 5 s task per tracked command accumulates for the life of the process.
- **B6. Queue panel refreshes always throw** "Model with key … not found", because no `modelMapper` is passed on refresh. The exception is swallowed (`MusicPlayer.kt:207-227`), so the queue panel never updates.
- **B7. Autocomplete answers every command's autocomplete** with `[]` (`Event.kt:120-139`). It is not scoped to `commandStringSet`.
- **B8. The history cap of 240 silently drops new tracks** when there is no played history to trim (`music/HistoryIndexManager.kt:175-206`, `// TODO: fix overflow tracks`). `/play` still reports success, and playlists longer than about 240 tracks are truncated without notice.
- **B9. Single-track loop combined with `LOAD_FAILED`** (`mayStartNext=true`) restarts the failing track forever (`music/TrackSchedulerCompat.kt:36-47`).
- **B10. No idle or auto-leave.**
  - The scheduler is never provided (`music/GuildMusicManager.kt:24`, `MusicPlayer.kt:777`).
  - Even if it ran, `onIdleTimeout` would only stop and clear, without disconnecting, while logging "Auto-disconnected" (`music/GuildMusicManager.kt:104-112`).
  - `player.auto_leave_timeout` is unused.
- **B11. Core's shared per-member substitutor is mutated** (`util/MusicPlayerUtils.kt:239`, `MusicPlayer.kt:622`). Music placeholders persist on the member and can leak into other plugins' templates. Core keys the substitutor by user id across guilds (`core:builtin/placeholder/Placeholder.kt:44-58`).
- **B12. Placeholder re-substitution (unverified but likely).** Commons-Text `StringSubstitutor` (`core:builtin/placeholder/Substitutor.kt`) re-scans substituted values by default.
  - A title or author containing `%user_name%`, or any other known key, would be expanded.
  - A value that contains its own placeholder would cause a cyclic-substitution exception.
  - `$%` sequences are treated as escapes.
- **B13. SoundCloud and Spotify artwork never shows.** The code calls `getUserData(String::class.java)` while userData is a Map (`util/MusicPlayerUtils.kt:210-218`), and it never uses lavaplayer's `AudioTrackInfo.artworkUrl`. YouTube `maxresdefault.jpg` is missing (404) for some videos.
- **B14. The userData Map collides with youtube-source.** youtube-source parses `userData` as JSON for token overrides, so every YouTube track start logs `Failed to parse token from userData` with a `JsonParseException` (log:3587; DEBUG level, harmless).
- **B15. Source registration hygiene and security.**
  - lavaplayer's deprecated YouTube manager is not excluded. youtube-source's README says it "must be disabled".
  - SoundCloud is registered twice.
  - The **HTTP source** lets any member make the bot GET arbitrary `http(s)` URLs, including internal addresses (SSRF-like). The response is limited to the error message.
  - The **local file source** is reachable for paths containing `youtube.com`, `youtu.be`, `soundcloud.com` or `spotify.com` (e.g. `/srv/spotify.com/a.mp3`), because those inputs skip the `ytsearch:` prefix.
- **B16. Guild managers and players are never destroyed.** Autocomplete and every command create them, and nothing destroys them (memory growth).
- **B17. `/skip` on the last track is a silent no-op** that re-shows the current track. `⏭️ 已跳過歌曲，播放清單已結束` is practically unreachable, and the skip button's equivalent is unacked (B3).
- **B18. Init failures are not caught.** `ExceptionInInitializerError` and `NoClassDefFoundError` are `Error`s, so `Event`'s `catch (e: Exception)` misses them and the plugin is bricked until restart. `MusicPlayerUtils` init also makes a blocking REST call on the event thread.
- **B19. Exceptions inside load callbacks leave "thinking…" up forever** (lavaplayer logs them and does not call `loadFailed`).
- **B20. The queue embed has no size limits.** Long queues or long titles exceed Discord's embed limits and lead to the generic error message.
- **B21. Progress-bar index overflow.** If `position > duration`, the index exceeds 14 and throws `ArrayIndexOutOfBounds` (`util/MusicPlayerUtils.kt:140-146`). This is an edge case.
- **B22. The previous button does not clear the paused flag, while skip does** (`music/GuildMusicManager.kt:223-225`).
- **B23. Unload leaks resources** (scheduler threads, lavaplayer pools, players). Reloading with `enabled: false` leaves playback and panel tasks running.
- **B24. Race on panel replacement.** When an old panel is deleted, `userTrackedMessages.remove(userId)` can drop the mapping of the user's newer panel (`MusicPlayer.kt:192-203`).
- **B25.** The result of `playTrack` is ignored in `trackLoaded` and `playlistLoaded`.
- **B26.** The autocomplete timeout (10 s) exceeds Discord's 3 s deadline.
- **B27.** `/play` checks CONNECT on the user's channel even when the bot is connected elsewhere and won't move.

### Behaviour to preserve, or to decide on explicitly in the spec
- **P1.** All command responses are **ephemeral**. `join`, `disconnect` and `stop` delete their response (silent success). Nothing is posted publicly, and there is no "now playing" announcement in the channel.
- **P2.** `/stop` both clears the queue and disconnects.
- **P3.** There is no DJ role and no permission model beyond the voice-presence checks:
  - `/play` and `/join` require the user to be in a VoiceChannel (not a Stage).
  - `/shuffle` and the buttons require the user to be in any voice channel.
  - Everything else, including `/stop`, `/disconnect`, `/volume` and `/skip`, works for any guild member, even outside voice.
  - Nowhere is the user required to be in the bot's channel.
- **P4.** `/play` while the bot is in another channel enqueues to the existing session and does not move the bot.
- **P5.** Non-URL input → `ytsearch:` first result. Real playlists enqueue every track. Search-result playlists enqueue only the first track.
- **P6.** History-index model: previous restarts the current track when position ≥ 5 s or there is no previous track; otherwise it goes back one track. Shuffle reorders only the upcoming tracks. Skip goes forward through the history.
- **P7.** Two loop modes (sequential ↔ single track), switchable **only through the button**. There is no queue loop, autoplay or seek. Shuffle is one-shot.
- **P8.** Panels refresh every 5 s, are deleted 60 s after creation, and each user has at most one live panel (a newer one deletes the older one).
- **P9.** Volume ranges 0–100 (lavaplayer units, 100 = unity) with a default of 40. It persists per guild until restart.
- **P10.** The embed and panel layout, the colours, the progress-bar format, and the zh-TW error strings.

### Dead code and unused items
- `util/MusicPlayerUtils.getSourceName` (152-159); `processSearchQuery` (164-172), which duplicates the inline routing.
- `music/GuildMusicManager`: `getStats`/`MusicStats`, `cleanup`, `totalPlaytimeMs`, `createdAt`, the idle-check path, and `isPlaying` used only for colour.
- `TrackSchedulerCompat.onTrackStart` (a no-op) and `clearHistory`, which is identical to `clearQueue`.
- `ConfigSerializer.getEnabledSources` / `getEnabledFeatures`, and about 35 unused config keys (§6).
- `EnhancedTrackInfo.isStream`, `source` and `MusicSource` are not used for rendering.
- The placeholders `track_duration`, `song_requester_name` and `song_requester_id` are not used by templates.
- `images/music_player__media_loop.png` and `images/music_player__media_shuffle.png` are unused.
- The `lavasrc-protocol` dependency is unused.
- `Event.kt:21` contains a stray `1`.
- `AudioPlayerSendHandler.close()` is reachable only from the dead `cleanup`.

### Hard-coded values
| Value | Location |
|---|---|
| Emoji IDs `1395593807352954950` (previous), `1395593823916265524` (pause_resume), `1395593814684471307` (next), `1395595107255844915` (disconnect) | every template with buttons |
| Fallback thumbnail `https://i.meee.com.tw/GHexAW6.png` | `util/MusicPlayerUtils.kt:246` |
| YouTube thumbnail pattern | `util/MusicPlayerUtils.kt:206` |
| Colours `0x68c06e`, `0xba9c55`, `0x9bd9d5`, `0x7fbf78` | code and templates |
| Previous-button threshold 5000 ms | `music/HistoryIndexManager.kt:13` |
| History cap 240 | `music/HistoryIndexManager.kt:14` |
| Search cache size 100 | `MusicPlayer.kt:76` |
| Autocomplete: minimum 2 characters, 10 results, 10 s timeout | `MusicPlayer.kt:241-245` |
| Panel 5 s / 60 s | `MusicPlayer.kt:181-183,192` |
| Progress-bar length 15 | `util/MusicPlayerUtils.kt:35` |
| Fallback volume 15 | `music/GuildMusicManager.kt:53` |
| Idle 10 min (dead) | `music/GuildMusicManager.kt:28` |
| Send buffer 1024 bytes | `music/AudioPlayerSendHandler.kt:13` |
| Scheduler pool of 2 | `MusicPlayer.kt:83` |
| Queue chunk of 10 | `MusicPlayer.kt:653` |

---

## 13. Testability

### Pure logic to extract (with test vectors taken from the Kotlin)
1. **`route_identifier(query)`** (`MusicPlayer.kt:401-407`).
   - `"never gonna"` → `"ytsearch:never gonna"`
   - `"https://youtu.be/x"` → unchanged
   - `"youtu.be/x"` → unchanged
   - `"www.youtube.com/watch?v=x"` → unchanged
   - `"soundcloud.com/a/b"` → unchanged
   - `"open.spotify.com/track/x"` → unchanged
   - `"httpfoo"` → unchanged (prefix rule)
   - `"scsearch:foo"` → `"ytsearch:scsearch:foo"`
2. **`is_search_identifier(id)`**: true when the id starts with `ytsearch:`, `scsearch:` or `ytmsearch:`. The search-result branch then enqueues only the first track.
3. **`format_time(ms)`** (`util/MusicPlayerUtils.kt:114-125`).
   - `0` → `00:00`
   - `59_999` → `00:59`
   - `60_000` → `01:00`
   - `3_599_999` → `59:59`
   - `3_600_000` → `01:00:00`
   - `360_000_000` → `100:00:00`
   - `Long.MAX_VALUE` → `∞ (直播)`
   - `-1` → `00:00`
4. **`progress_bar(pos, dur, playing, emojis)`** (`util/MusicPlayerUtils.kt:38-49,130-147`).
   - If `dur == Long.MAX_VALUE` or `dur ≤ 0`: `"{play|pause} 直播中"`.
   - Otherwise `i = floor(pos/dur*14)` and the output is `"{play|pause} " + fmt(pos) + BAR[i] + fmt(dur)`. There are no spaces around BAR.
   - `BAR[0] = ws + b×13 + be`; `BAR[k] = ws + wf×k + b×(13−k) + be` for k in 1..13; `BAR[14] = ws + wf×13 + we`. Each bar is 15 emojis.
   - Vectors: `pos = 0` → i 0; `pos = dur/2` → i 7; `pos = dur` → i 14; `pos > dur` → overflow (B21).
5. **`extract_youtube_video_id(url)`**.
   - `https://www.youtube.com/watch?v=dQw4w9WgXcQ` → `dQw4w9WgXcQ`
   - `https://youtu.be/abc_-1?t=3` → `abc_-1`
   - `https://www.youtube.com/embed/xyz` → `xyz`
   - `https://youtube.com/v/xyz` → `xyz`
   - `https://youtube.com.br/watch?v=id` → `id`
   - `https://www.youtube.com/watch?feature=a&v=id` → no match (the code falls back to `info.identifier`)
   - non-YouTube → none
6. **Artwork, colour and loop emoji selection** (§7 table).
7. **History state machine** (`music/HistoryIndexManager.kt`), using a fake player that offers `start_track`, `playing`, `position` and `paused`.
   - add to empty → starts at index 0
   - add to non-empty → append only (B1)
   - skip at the end → False, index unchanged
   - previous with position ≥ 5000 → restart
   - previous with position < 5000 and index > 0 → index−1
   - previous at index 0 → restart
   - shuffle with ≤1 upcoming → False
   - trim at 241 when index = 0 → drops the newest (B8); when index > 0 → drops the oldest and shifts the index
   - track end: FINISHED or LOAD_FAILED advances; STOPPED, REPLACED or CLEANUP do nothing; single-loop restarts
8. **Skip-count validation:** `max = upcoming + 1`. With history `[A,B,C,D]` at index 0: `count = 2` → C; `count = 4` → D (the last skip is a no-op); `count = 5` → `❌ 只能跳過 4 首歌曲！`.
9. **Loop toggle:** sequential → single → sequential.
10. **Queue embed builder:** chunks of 10, numbering continues across chunks, line format as in §3, field name `—`, colour `0x9bd9d5`.
11. **Autocomplete formatting:** minimum length 2, at most 10 choices, `name[:100]`, value = uri, cache hit on the exact key, FIFO eviction past 100 entries.
12. **custom_id:** `build({"action": "skip"}) == "musicplayer@a:skip"`, and `parse` round-trips. Unknown short keys or a missing prefix raise.
13. **Config schema** (e.g. pydantic, `extra="forbid"`): every per-field rule and the three `validate()` cross-rules in §6.
14. **Panel tracker,** with a fake clock and scheduler: the first refresh at +5 s; deletion when `now − created ≥ 60 s`; one panel per user; no edit while idle; a refresh re-renders the current track with the original template key.

### Parts that need Discord or audio test doubles
- Interaction: `defer(ephemeral)`, `edit_original_response`, `delete_original_response`, and the component `defer` (deferEdit).
- Member voice state and channel type.
- `guild.me` permissions for the channel.
- Voice client: `connect`, `move_to`, `disconnect`, `is_connected`.
- Application emoji fetch.
- Audio backend: load results (track, playlist, search playlist, no matches, failed) and end-of-track events carrying a `may_start_next` reason.
- Python equivalents of Core's auto-defer and prefix router.

---

## 14. Porting assessment

**Difficulty: High.**
- The command surface is small (11 commands, 5 buttons, no persistence).
- The whole audio stack must be replaced: lavaplayer + youtube-source + lavasrc + JDA audio + JDAVE.
- Voice now **requires DAVE E2EE**. Discord closes non-DAVE voice sessions with close code 4017 "E2EE/DAVE protocol required"; log:836-861 shows the join/leave cycling before Core adopted JDAVE.
- YouTube extraction is fragile.
- The progress bar needs playback position tracking.
- Panels need careful interaction-lifecycle handling.
- Application emojis have to be provisioned.

### Suggested discord.py mapping
- **Cog** `MusicPlayer(commands.Cog)` with 11 `@app_commands.command`s, guild-scoped (or global with `guild_only`).
  - Localize names and descriptions through an `app_commands.Translator` that loads `register.yaml` (en-US and zh-TW).
  - Options: `query: str` (`max_length=500`, `@autocomplete`); `count: app_commands.Range[int, 1, 50] = 1`; `level: app_commands.Range[int, 0, 100]` (`@autocomplete`).
  - `default_permissions=None`.
- **Auto-defer:** mirror Core with a pre-dispatch `await interaction.response.defer(ephemeral=True, thinking=True)` and keep a configurable switch. All replies then go through `interaction.edit_original_response` or `delete_original_response`.
- **Buttons:** `discord.ui.DynamicItem[discord.ui.Button]` with template `musicplayer@a:(?P<action>previous|pause-resume|skip|loop|disconnect)` (added through `bot.add_dynamic_items`), or a core-level prefix router in `on_interaction`.
  - Acknowledge with `await interaction.response.defer()` (deferred update) before any edit. This fixes B3; if the spec needs strict parity, record "interaction failed" as the legacy behaviour.
- **Panels:**
  - One `asyncio.Task` per panel: loop with `await asyncio.sleep(5)` and `edit_original_response`; delete at 60 s.
  - Keep a `dict[user_id, PanelTask]` and cancel the old task on replacement (fixes B5).
  - Decide whether clicks extend the life (B4).
- **Audio backend abstraction** (`Protocol`): `load(identifier) -> LoadResult`, `start/stop/pause/resume/set_volume/position/current`, and `on_track_end(reason)`. Unit-test the queue and history logic against a fake backend.
  - **Option A — Lavalink ≥ 4.2** (DAVE support added in 4.2.0; DAVE requires glibc ≥ 2.35 on the node), with the youtube-source and LavaSrc plugins. Python clients listed as DAVE-capable on lavalink.dev include lavalink.py, Mafic and Pomice; wavelink's status is unconfirmed. This option is semantically closest: `ytsearch:`, playlists, track positions, lavaplayer volume units, and end reasons with `mayStartNext`. The cost is a separate JVM service.
  - **Option B — native `discord.py[voice] ≥ 2.7`**. DAVE support arrived in 2.7.0 (GH-10300) through `davey`, which the `voice` extra pins as `PyNaCl>=1.6,<1.7` plus `davey>=0.1.0`; davey 0.1.6 ships cp314 wheels for Linux, musllinux, macOS and Windows. The rest of the stack would be:
    - yt-dlp for extraction (full YouTube support now needs a JS runtime such as Deno through EJS);
    - FFmpeg for decoding;
    - libopus for encoding PCM when `PCMVolumeTransformer` is used;
    - a frame-counting `AudioSource` wrapper for position;
    - re-spawning FFmpeg for restart/previous;
    - Spotify through the Web API plus mirroring to a YouTube search;
    - marshalling `after` callbacks onto the event loop with `run_coroutine_threadsafe`.
- **Voice-state handling:** none exists today. Add `on_voice_state_update` only if the spec chooses to fix B10 and handle kicks.
- **Emojis:** resolve all 13 by name with `fetch_application_emojis()` at startup and fail fast.
- **Risks:**
  1. YouTube blocking and extraction drift (OAuth/poToken for youtube-source; JS runtime and PO tokens for yt-dlp).
  2. DAVE dependencies (wheel availability, Lavalink version, glibc).
  3. The 3 s autocomplete deadline when searching through yt-dlp.
  4. Position and progress parity.
  5. Reproducing quirks such as B1 and B2 versus fixing them.
  6. CPU cost: Opus re-encoding happens whenever volume ≠ 100 (lavaplayer log:3618), and FFmpeg costs more.
  7. Security of arbitrary URLs and local files (B15). Restrict the sources in the port.

---

## Appendix A: voice stack (Core + MusicPlayer + AudioAPI), as found on `main`

### Pipeline (in-process JVM; **not Lavalink**)
1. **lavaplayer 2.2.6** (`dev.arbjerg`) loads and decodes the source.
   - Opus sources are passed through. When volume ≠ 100, lavaplayer re-encodes: log:3618 shows "Enabling reencode mode on opus track" at the default volume of 40.
2. `music/AudioPlayerSendHandler` (`isOpus() = true`) hands JDA one 20 ms Opus frame per poll (`canProvide()` → `audioPlayer.provide(frame)` into a 1024-byte buffer; `provide20MsAudio()` returns a duplicate of that buffer).
3. **JDA 6.4.1 AudioManager** sends the frames with JDA's default Java send system.
   - udpqueue (`NativeAudioSendFactory`) is declared in `gradle/libs.versions.toml:19,63-71` but used by **no** build file.
   - The config value `performance.audio_send_system: NAS` is not wired to anything.
4. **DAVE E2EE** comes from JDAVE/libdave, followed by JDA's RTP transport encryption.
   - Transport uses AEAD modes. tink (XChaCha20) is presumably on Core's classpath through JDA's transitive dependencies (**unverified** for the `main` build; see AudioAPI.md).
- The `maven.lavalink.dev` repository is used only to fetch youtube-source. There is no Lavalink node or client.

### Sources
| Source | Notes |
|---|---|
| youtube-source 1.17.0 `common` | Search, video IDs and playlist IDs allowed. Observed InnerTube client `ANDROID_VR` with the local signature cipher (log:3570-3612). No OAuth, poToken or remote cipher. |
| lavaplayer SoundCloud | Registered twice |
| lavasrc 4.8.1 Spotify | Opt-in. Default providers mirror to `ytsearch:` (**unverified**). |
| Other lavaplayer remote sources | Deprecated built-in YouTube, Yandex, Bandcamp, Vimeo, Twitch, Beam, Getyarn, Niconico, HTTP |
| Local files | `registerLocalSource` |

### DAVE configuration in Core
- `core:base/BotLoader.kt:56-60`:
  `JDABuilder.createDefault(token).setAudioModuleConfig(AudioModuleConfig().withDaveSessionFactory(JDaveSessionFactory()))`
- Added in commit ff1b68f (2026-04-07): "Fixes voice join/leave cycling caused by Discord rejecting non-DAVE connections".
- Dependencies:
  - `club.minnced:jdave-api:0.1.8`
  - natives `jdave-native-{linux-x86-64, linux-aarch64, win-x86-64, darwin}` (`Core/build.gradle.kts:72-76`, `gradle/libs.versions.toml:9,72-76`)
- Runtime requirements:
  - JDAVE needs **Java 25** (it uses FFM).
  - Core's shadow-jar manifest sets `Enable-Native-Access: ALL-UNNAMED` (`Core/build.gradle.kts:98-103`).
  - The build toolchain is 25, although the README still says "Java 21+".
- DAVE is always on; there is no config switch.
- Platforms with no bundled libdave (musl/Alpine, 32-bit, Windows ARM) would need `-Djdave.library.path=…` (JDAVE README) or would lose voice.
- **Runtime evidence** (log, 2026-04-07):
  - Before JDAVE: WARN "Using passthrough dave session. Please migrate to an implementation of libdave! Your audio connections will stop working on 2026-03-01." (log:836)
  - "Maximum Dave Protocol Version is 0" (log:857).
  - The voice WS closed with **4017 "E2EE/DAVE protocol required"** (log:860-861), then 4003/4006 and repeated rejoins (log:864-931).
  - After JDAVE: an MLS commit and a protocol transition to v1, and libdave reports "Encrypted audio: N … Failed audio: 0" (log ~3555-3567, ~3620+).

### Voice-state handling, idle and auto-disconnect
- No `GuildVoiceUpdateEvent` handling.
- No auto-leave (B10).
- If nobody polls the player for 1 min, lavaplayer's default player cleanup stops the track with `CLEANUP`.

### What a Python port would need
1. **DAVE is mandatory.**
   - discord.py **≥ 2.7.0** added "DAVE protocol support for voice connections" (GH-10300). Its `voice` extra is `PyNaCl>=1.6.0,<1.7` plus `davey>=0.1.0`. 2.7.1 raises an error and warns when `davey` is missing during voice use, and adds davey details to `python -m discord --version`.
   - davey 0.1.6 (2026-06-22) ships CPython 3.14 wheels for manylinux (x86_64, aarch64, …), musllinux, macOS (x86_64, arm64) and Windows.
   - discord.py needs `audioop-lts` on Python ≥ 3.13; its `requirements.txt` already includes it.
   - discord.py 2.7.1's PyPI classifiers stop at 3.12, while `requires_python` is ≥ 3.8. Verify on 3.14.
2. **Pick an audio backend.**
   - **(A) Lavalink ≥ 4.2.0.** The release notes list DAVE support and a mandatory voice-state `channelId`. DAVE needs glibc ≥ 2.35 on the node. Add the youtube-source plugin, plus LavaSrc for Spotify. Use a DAVE-capable Python client: the lavalink.dev clients page marks lavalink.py, Mafic, Pomice, lavaplay.py and lavalink-rs as supporting DAVE; wavelink's status is unconfirmed. This keeps lavaplayer semantics (identifiers, playlists, position, volume units, end reasons).
   - **(B) Native discord.py voice.** Needs FFmpeg; yt-dlp, which since 2025.11 needs a JS runtime such as Deno, plus the EJS solver package, for full YouTube support; and libopus for PCM paths (`PCMVolumeTransformer`). You would also reimplement the parts lavaplayer currently provides:
     - search and playlist expansion;
     - position tracking by counting frames;
     - restart/previous by re-spawning FFmpeg;
     - Spotify mirroring.
3. **In both cases:**
   - Keep `voice_states` intents and voice member caching on.
   - Keep self_deaf/self_mute off, which the current behaviour expects.
   - Provision application emojis.
   - Restrict HTTP and local sources.
