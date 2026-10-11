## 1. Reload feedback

- [x] 1.1 xfail tests for "Reloads upload the commands and never overlap" (the summary is logged
      before the first upload; a reload that waits logs it)
- [x] 1.2 Log the summary before the upload and the waiting line; remove the markers

## 2. Console and image

- [x] 2.1 xfail tests for "Console completion" (no lines kept free below the prompt, no cursor move
      up) and "No cursor position requests" (`PROMPT_TOOLKIT_NO_CPR=1`)
- [x] 2.2 readline-like completion and the image's variable; remove the markers

## 3. Voice warnings

- [x] 3.1 xfail test for "No voice warnings at startup"
- [x] 3.2 Turn the warnings off in `Bot.__init__`; remove the marker

## 4. Close

- [x] 4.1 Gate passes, push, CI green
- [x] 4.2 The manual check on the owner's Mac (design, "Manual check")
- [x] 4.3 Archive the change and run `openspec validate --all --strict`; update `HANDOFF.md`
