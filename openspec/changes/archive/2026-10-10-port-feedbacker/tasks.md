## 1. Core templates

- [x] 1.1 xfail tests for "Embed fields follow JDA" (no stub can raise inside the renderer, so the
      marker has no `raises`)
- [x] 1.2 Trim fields and give empty ones U+200E in `render_message`; remove the markers
- [x] 1.3 xfail tests for "Modal submissions are read back" against a stub `modal_values`
- [x] 1.4 Implement `modal_values` and export it from `xincord.core.templates`; remove the markers

## 2. Resources

- [x] 2.1 Bundle v3's en-US and zh-TW lang files with LF line endings, and `config.yaml` with v3's
      replies and the two new ones

## 3. Installation

- [x] 3.1 xfail tests for "The plugin installs as Feedbacker"
- [x] 3.2 Add the package, its `setup` and the `Feedbacker` entry point; remove the markers

## 4. Config

- [x] 4.1 xfail tests for "The config holds the replies"
- [x] 4.2 Add the replies with v3's keys, the new defaults and the length check; remove the
      markers

## 5. Stars

- [x] 5.1 xfail tests for "Stars follow v3's text" against stubs `stars` and `star_count` in
      `form.py`
- [x] 5.2 Implement them; remove the markers

## 6. Creating a form

- [x] 6.1 xfail tests for "Administrators post a feedback form", "Only administrators post forms"
      and "A form that cannot be posted is reported", against a stub `create_form`
- [x] 6.2 Implement `create_form`; remove the markers

## 7. Pressing a star

- [x] 7.1 xfail tests for "Only the rated member presses a star" and "A star opens the feedback
      modal", against stubs `press_star` and `highlight`
- [x] 7.2 Implement them; remove the markers

## 8. Submitting a feedback

- [x] 8.1 xfail tests for "A submitted feedback is posted" and "A feedback that cannot be posted
      keeps the form", against a stub `submit_form`
- [x] 8.2 Implement `submit_form`; remove the markers

## 9. Command and routes

- [x] 9.1 xfail tests for "The command is a localized guild command" and "v3's forms keep working"
- [x] 9.2 Build the command, register it and route `IDS` to `handle` in `setup`; remove the markers

## 10. Conventions and docs

- [x] 10.1 Check that the built wheel ships `config.yaml` and `lang/` and that `xincord --no-online`
      loads the plugin; drive it once through discord.py's own objects
- [x] 10.2 Porting guide rows and pitfalls, and skill corrections
- [x] 10.3 Audit the inventory against the scenarios and the design

## 11. Close

- [x] 11.1 Gate passes, push, CI green
- [x] 11.2 Archive the change and run `openspec validate --all --strict`
- [x] 11.3 Update `HANDOFF.md` and `docs/porting/owner-review.md`; push; CI green
