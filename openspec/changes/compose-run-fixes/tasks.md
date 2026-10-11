## 1. Reload feedback

- [ ] 1.1 xfail tests for "Reloads upload the commands and never overlap" (the summary is logged
      before the first upload; a reload that waits logs it)
- [ ] 1.2 Log the summary before the upload and the waiting line; remove the markers

## 2. Console and image

- [ ] 2.1 xfail tests for "Console completion" (no lines kept free below the prompt, no cursor move
      up) and "Container image" (`PROMPT_TOOLKIT_NO_CPR=1`)
- [ ] 2.2 readline-like completion and the image's variable; remove the markers

## 3. Voice warnings

- [ ] 3.1 xfail test for "Startup loads the configured plugins" (no voice warnings)
- [ ] 3.2 Turn the warnings off in `Bot.__init__`; remove the marker

## 4. Close

- [ ] 4.1 Gate passes, push, CI green
- [ ] 4.2 The manual check on the owner's Mac (design, "Manual check")
- [ ] 4.3 Archive the change and run `openspec validate --all --strict`; update `HANDOFF.md`
