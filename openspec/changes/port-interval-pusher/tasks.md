## 1. Resources

- [ ] 1.1 Bundle `config.yaml` with no listeners and a commented example on `status.example.com`
      (v3's file pushed to the owner's status domain)

## 2. Installation

- [ ] 2.1 xfail tests for "The plugin installs as IntervalPusher"
- [ ] 2.2 Add the package, its `setup` and the `IntervalPusher` entry point; remove the markers

## 3. Config

- [ ] 3.1 xfail tests for "The config lists the URLs to push"
- [ ] 3.2 Add the listener model with v3's keys, the interval range and the URL check; remove the
      markers

## 4. REST ping

- [ ] 4.1 xfail tests for "The URL carries the REST ping" against stubs in `pusher.py`
- [ ] 4.2 Implement `build_url`, `rest_ping` and `Pusher.url`, and declare aiohttp in
      `xincord-plugins`; remove the markers

## 5. Push request

- [ ] 5.1 xfail tests for "Each push is one GET request", with the local monitor in
      `tests/support/http_fakes.py`
- [ ] 5.2 Implement `open_session` and `get_status`; remove the markers

## 6. Status codes

- [ ] 6.1 xfail tests for "The status code decides what follows" against a stub `Pusher.push`
- [ ] 6.2 Implement `Pusher.push`; remove the markers

## 7. Loop

- [ ] 7.1 xfail tests for "Each listener pushes at once, then after a fixed delay" against a stub
      `Pusher.run` (the independent listeners are tested with the cog, in 8.1)
- [ ] 7.2 Implement `Pusher.run`; remove the markers

## 8. Lifecycle

- [ ] 8.1 xfail tests for "Pushing follows the bot's readiness and the plugin's lifetime" and for
      independent listeners, against a stub `tasks`
- [ ] 8.2 Start the loops in `cog_load` and cancel them in `cog_unload`; remove the markers

## 9. Conventions and docs

- [ ] 9.1 Check that the built wheel ships `config.yaml` and that `xincord --no-online` loads the
      plugin; drive it once through discord.py's own objects
- [ ] 9.2 Porting guide rows and pitfalls, and skill corrections (background loops, outgoing HTTP,
      the new test helpers)
- [ ] 9.3 Audit the inventory against the scenarios and the design

## 10. Close

- [ ] 10.1 Gate passes, push, CI green
- [ ] 10.2 Archive the change and run `openspec validate --all --strict`
- [ ] 10.3 Update `HANDOFF.md` and `docs/porting/owner-review.md`; push; CI green
